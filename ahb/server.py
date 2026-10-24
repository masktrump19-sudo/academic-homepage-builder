"""Loopback-only wizard. Resumes, attachments and previews stay in memory."""
from collections import OrderedDict
from io import BytesIO
from pathlib import Path, PurePosixPath
import json
import mimetypes
import secrets
import time
import zipfile
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.formparsers import MultiPartParser
from .models import Site, blank_site
from .assets import MAX_UPLOAD, sanitize_attachment, valid_asset_path
from .parser import parse_resume, parse_text
from .exporter import public_files, source_files, make_zip, asset_references

PACKAGE = Path(__file__).resolve().parent
# Bodies are bounded before multipart parsing; uploaded files never roll onto disk.
MAX_REQUEST = MAX_UPLOAD * 5
MultiPartParser.spool_max_size = MAX_REQUEST + 1


def create_app() -> FastAPI:
    app = FastAPI(title='Academic Homepage Builder', docs_url=None, redoc_url=None, openapi_url=None)
    token = secrets.token_urlsafe(32)
    assets: dict[str, dict] = {}
    previews: OrderedDict[str, tuple[float, dict[str, bytes]]] = OrderedDict()
    app.state.token, app.state.assets = token, assets

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        if request.url.hostname not in {'127.0.0.1', 'localhost', 'testserver'}:
            return JSONResponse({'detail': 'This wizard accepts only local requests.'}, 403)
        origin = request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': 'Cross-origin requests are disabled.'}, 403)
        length = request.headers.get('content-length', '0')
        if not length.isdecimal() or int(length) > MAX_REQUEST:
            return JSONResponse({'detail': 'Request is too large.'}, 413)
        if request.method not in {'GET', 'HEAD'} and not secrets.compare_digest(request.headers.get('x-ahb-token', ''), token):
            return JSONResponse({'detail': 'Reload the local wizard before continuing.'}, 403)
        if request.method not in {'GET', 'HEAD'}:
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_REQUEST:
                    return JSONResponse({'detail': 'Request is too large.'}, 413)
                body.extend(chunk)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'"
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        if isinstance(exc, ValidationError):
            fields = ['.'.join(str(x) for x in e['loc']) + ': ' + e['msg'] for e in exc.errors(include_input=False, include_url=False)[:8]]
            return JSONResponse({'detail': '; '.join(fields)}, 422)
        return JSONResponse({'detail': str(exc)}, 422)

    @app.exception_handler(RequestValidationError)
    async def request_error(request, exc):
        return JSONResponse({'detail': 'The request is incomplete or has an invalid format.'}, 422)

    def demo():
        path = PACKAGE / 'demo.json'
        return json.loads(path.read_text(encoding='utf8')) if path.exists() else blank_site().model_dump(mode='json')

    @app.get('/')
    async def index():
        return HTMLResponse((PACKAGE / 'web/index.html').read_text(encoding='utf8'))

    @app.get('/web/{filename}')
    async def web_file(filename: str):
        path = PACKAGE / 'web' / filename
        if Path(filename).name != filename or path.suffix not in {'.css', '.js', '.svg'} or not path.is_file():
            return Response(status_code=404)
        return Response(path.read_bytes(), media_type=mimetypes.guess_type(filename)[0])

    @app.get('/api/config')
    async def config():
        return {'token': token, 'schema': Site.model_json_schema(), 'blank': blank_site().model_dump(mode='json'), 'demo': demo()}

    async def json_object(request: Request) -> dict:
        try:
            data = await request.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError('Send a valid JSON object.') from exc
        if not isinstance(data, dict):
            raise ValueError('The request must be a JSON object.')
        return data

    @app.post('/api/parse')
    async def parse(file: UploadFile = File(...)):
        data = await file.read(MAX_UPLOAD + 1)
        await file.close()
        if len(data) > MAX_UPLOAD:
            raise ValueError('Resume must be smaller than 20 MB.')
        return parse_resume(file.filename or '', data)

    @app.post('/api/parse-text')
    async def parse_paste(request: Request):
        data = await json_object(request)
        text = data.get('text', '')
        if not isinstance(text, str) or len(text) > 150000:
            raise ValueError('Paste at most 150,000 characters.')
        return parse_text(text)

    def add_asset(name: str, payload: bytes, path: str | None = None):
        content, suffix, mime = sanitize_attachment(name, payload)
        if len(assets) >= 60 or sum(len(a['data']) for a in assets.values()) + len(content) > 100 * 1024 * 1024:
            raise ValueError('Session attachment limit reached. Clear the session before importing another project.')
        id_ = secrets.token_hex(12)
        path = path or 'assets/uploads/' + id_ + suffix
        if not valid_asset_path(path):
            raise ValueError('Invalid attachment path.')
        asset = {'id': id_, 'path': path, 'name': PurePosixPath(name.replace('\\', '/')).name, 'mime': mime, 'size': len(content), 'data': content}
        assets[id_] = asset
        return {k: v for k, v in asset.items() if k != 'data'}

    @app.post('/api/assets')
    async def upload_asset(file: UploadFile = File(...)):
        payload = await file.read(MAX_UPLOAD + 1)
        await file.close()
        return add_asset(file.filename or '', payload)

    def selected(data: dict):
        site = Site.model_validate(data.get('site', {}))
        ids = data.get('asset_ids', [])
        if not isinstance(ids, list) or any(not isinstance(i, str) or i not in assets for i in ids):
            raise ValueError('An attachment is unavailable. Select it again.')
        return site, {assets[i]['path']: assets[i]['data'] for i in ids}

    @app.post('/api/preview')
    async def preview(request: Request):
        site, media = selected(await json_object(request))
        files = public_files(site, media, reviewed=False)
        for id_ in list(previews):
            if time.monotonic() - previews[id_][0] > 3600:
                previews.pop(id_)
        while len(previews) >= 4:
            previews.popitem(last=False)
        id_ = secrets.token_urlsafe(24)
        previews[id_] = (time.monotonic(), files)
        return {'url': f'/preview/{id_}/index.html'}

    @app.get('/preview/{id_}/{filename:path}')
    async def preview_file(id_: str, filename: str):
        record = previews.get(id_)
        if not record or time.monotonic() - record[0] > 3600 or filename not in record[1]:
            return Response(status_code=404)
        return Response(record[1][filename], media_type=mimetypes.guess_type(filename)[0] or 'application/octet-stream')

    @app.post('/api/export')
    async def export(request: Request):
        data = await json_object(request)
        if data.get('reviewed') is not True:
            raise ValueError('Review the public content and attachments before exporting.')
        site, media = selected(data)
        kind = data.get('kind', 'static')
        if not isinstance(kind, str) or kind not in {'source', 'static'}:
            raise ValueError('Choose a static website or editable source export.')
        files = source_files(site, media) if kind == 'source' else public_files(site, media)
        return Response(make_zip(files), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="academic-homepage-{kind}.zip"'})

    @app.post('/api/import')
    async def import_project(file: UploadFile = File(...)):
        payload = await file.read(MAX_UPLOAD * 4 + 1)
        await file.close()
        if len(payload) > MAX_UPLOAD * 4:
            raise ValueError('Project import is limited to 80 MB.')
        imported = []
        if (file.filename or '').lower().endswith('.json'):
            site = Site.model_validate_json(payload)
        elif (file.filename or '').lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(BytesIO(payload)) as archive:
                    entries = archive.infolist()
                    if len(entries) > 300 or sum(i.file_size for i in entries) > MAX_UPLOAD * 5:
                        raise ValueError('Project archive exceeds the import limits.')
                    names = [i.filename for i in entries]
                    if len(names) != len(set(names)) or 'site.json' not in names:
                        raise ValueError('Choose a source ZIP containing one site.json at its root.')
                    for i in entries:
                        path = PurePosixPath(i.filename)
                        if path.is_absolute() or '..' in path.parts or '\\' in i.filename or i.flag_bits & 1 or (i.external_attr >> 16) & 0o170000 == 0o120000:
                            raise ValueError('Unsafe paths or encrypted entries in project archive.')
                        if i.file_size > MAX_UPLOAD or i.file_size > max(1, i.compress_size) * 200:
                            raise ValueError('Archive entry exceeds safe extraction limits.')
                    site = Site.model_validate_json(archive.read('site.json'))
                    refs = asset_references(site)
                    for name in refs:
                        if name not in names:
                            raise ValueError('Referenced attachment is missing from the source ZIP.')
                    before = set(assets)
                    try:
                        for name in refs:
                            imported.append(add_asset(name, archive.read(name), name))
                    except Exception:
                        for key in set(assets) - before:
                            del assets[key]
                        raise
            except zipfile.BadZipFile as exc:
                raise ValueError('This source ZIP is damaged.') from exc
        else:
            raise ValueError('Import an AHB source ZIP or site.json.')
        for entries in site.sections.values():
            for entry in entries:
                entry.confirmed = False
        return {'site': site.model_dump(mode='json'), 'assets': imported, 'warnings': ['Review imported content and explicitly select public attachments before export.']}

    @app.get('/api/codex/status')
    async def codex_status():
        from .ai import status
        import asyncio
        return await asyncio.to_thread(status)

    @app.post('/api/assist-pack')
    async def assist_pack(request: Request):
        from .ai import collaboration_pack
        data = await json_object(request)
        output = collaboration_pack(data.get('text', ''), data.get('languages', ['en']))
        return Response(output, media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="ai-collaboration-pack.zip"'})

    @app.post('/api/ai')
    async def ai(request: Request):
        from .ai import generate
        import asyncio
        data = await json_object(request)
        if data.get('consent') is not True:
            raise ValueError('Confirm the selected text may be sent to your configured Codex provider.')
        return await asyncio.to_thread(generate, data.get('text', ''), data.get('languages', ['en']), data.get('model'))

    @app.delete('/api/session')
    async def clear_session():
        assets.clear()
        previews.clear()
        return {'cleared': True}

    return app

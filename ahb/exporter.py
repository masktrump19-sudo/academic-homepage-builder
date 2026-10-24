"""Build only reviewed public files; isolated outputs prevent cross-project leaks."""
from io import BytesIO
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
import hashlib
import json
import shutil
import uuid
import zipfile
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
from .models import Site
from .assets import valid_asset_path, sanitize_attachment, MAX_UPLOAD

MARKER = '.ahb-generated'


def public_site(site: Site) -> Site:
    data = site.model_dump(mode='json')
    data['sections'] = {key: [entry for entry in entries if entry['enabled']]
                        for key, entries in data['sections'].items() if key not in site.hidden_sections}
    if 'about' in site.hidden_sections:
        data['profile']['bio'] = {}
        data['profile']['interests'] = {}
    if 'contact' in site.hidden_sections:
        data['contact'] = {}
        data['hobbies'] = {}
    def remove_unused_language(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {'en', 'zh'} and isinstance(child, str) and key not in site.languages:
                    value[key] = ''
                else:
                    remove_unused_language(child)
        elif isinstance(value, list):
            for child in value:
                remove_unused_language(child)
    remove_unused_language(data)
    return Site.model_validate(data)


def asset_references(site: Site) -> set[str]:
    refs = {site.profile.portrait, site.profile.cv}
    for entries in site.sections.values():
        refs.update(e.image for e in entries if e.enabled)
    return {p for p in refs if p}


def _prepare_public(site: Site, assets: dict[str, bytes], *, reviewed: bool = True) -> tuple[Site, dict[str, bytes]]:
    """Validate and sanitize the same public data for UI, CLI and source exports."""
    site = public_site(Site.model_validate(site.model_dump(mode='json')))
    if reviewed:
        pending = [k for k, entries in site.sections.items() if k not in site.hidden_sections for e in entries if e.enabled and not e.confirmed]
        if pending:
            raise ValueError('Review and confirm enabled entries before exporting: ' + ', '.join(sorted(set(pending))))
        for lang in site.languages:
            if not site.profile.name.get(lang, '').strip():
                raise ValueError('Add a name for every enabled language before exporting.')
    references = asset_references(site)
    missing = references - set(assets)
    if missing:
        raise ValueError('Select the public attachments referenced by this site before exporting.')
    public_assets, renamed = {}, {}
    for path in sorted(references):
        content = assets[path]
        if not valid_asset_path(path) or not isinstance(content, bytes) or len(content) > MAX_UPLOAD:
            raise ValueError('Invalid public attachment path or size.')
        content, suffix, _ = sanitize_attachment(path, content)
        target = str(PurePosixPath(path).with_suffix(suffix))
        if target != path and (target in references or target in public_assets):
            target = 'assets/uploads/' + hashlib.sha256(content).hexdigest() + suffix
        if target in public_assets and public_assets[target] != content:
            raise ValueError('Conflicting attachment filenames. Rename one attachment before exporting.')
        public_assets[target], renamed[path] = content, target
    site.profile.portrait = renamed.get(site.profile.portrait, '')
    site.profile.cv = renamed.get(site.profile.cv, '')
    for entries in site.sections.values():
        for entry in entries:
            entry.image = renamed.get(entry.image, '')
    return site, public_assets


def public_files(site: Site, assets: dict[str, bytes], *, reviewed: bool = True) -> dict[str, bytes]:
    from .render import render_site
    site, assets = _prepare_public(site, assets, reviewed=reviewed)
    files = render_site(site)
    for path, content in files.items():
        if PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts or '\\' in path or not isinstance(content, bytes):
            raise ValueError('Renderer returned an unsafe output path.')
    files.update(assets)
    files[MARKER] = b'Academic Homepage Builder generated directory\n'
    return files


def make_zip(files: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(files.items()):
            archive.writestr(path, content)
    return output.getvalue()


def source_files(site: Site, assets: dict[str, bytes]) -> dict[str, bytes]:
    # Run the release checks before packing a source project too.
    site, assets = _prepare_public(site, assets)
    package = Path(__file__).resolve().parent
    files = dict(assets)
    files['site.json'] = (json.dumps(public_site(site).model_dump(mode='json'), ensure_ascii=False, indent=2) + '\n').encode()
    for name in ['__init__.py', 'models.py', 'render.py', 'assets.py', 'exporter.py']:
        files['ahb/' + name] = (package / name).read_bytes()
    for path in (package / 'site_assets').iterdir():
        if path.is_file() and path.suffix in {'.css', '.js', '.svg', '.txt', '.woff2'}:
            files['ahb/site_assets/' + path.name] = path.read_bytes()
    root = package.parent
    for name in ['LICENSE', 'THIRD_PARTY_NOTICES.md']:
        # A wheel lives inside site-packages, not beside the repository notices.
        # Standalone source exports keep these notices at their project root.
        notice = package / 'licenses' / name
        if not notice.is_file():
            notice = root / name
        if not notice.is_file():
            raise ValueError('Required license notice is missing. Reinstall Academic Homepage Builder.')
        files[name] = notice.read_bytes()
    files['requirements.txt'] = b'pydantic>=2.10,<3\nPillow>=11\npypdf>=6\n'
    lock = root / 'requirements.txt'
    if lock.exists():
        # Only the dependencies needed to build this standalone static project.
        prefixes = ('pydantic==', 'pydantic-core==', 'annotated-types==', 'typing-extensions==', 'typing-inspection==', 'pillow==', 'pypdf==')
        lines = [line for line in lock.read_text().splitlines() if line.lower().replace('_', '-').startswith(prefixes)]
        if len(lines) >= 3:
            files['requirements.txt'] = ('\n'.join(lines) + '\n').encode()
    files['build.py'] = b'''from pathlib import Path
from ahb.exporter import load_project, build_project
root = Path(__file__).resolve().parent
site, assets = load_project(root)
build_project(site, assets, root / "dist")
print("Built dist/. Verify your actual site URL before publishing.")
'''
    files['.gitignore'] = b'.venv/\n__pycache__/\n*.pyc\ndist/\n.env*\n'
    files['.python-version'] = b'3.12\n'
    files['README.md'] = b'''# My academic homepage

This project contains only the site content and attachments you explicitly selected.
Review site.json and assets/uploads before making the repository public.

Build: `pip install -r requirements.txt` then `python build.py`.
Preview: `python -m http.server 8000 --directory dist --bind 127.0.0.1`.

Cloudflare Pages: connect your own GitHub repository (Git integration), choose
Python 3.12, build command `pip install -r requirements.txt && python build.py`,
and output directory `dist`. Choose your repository visibility yourself.
After Pages assigns the real HTTPS address, set site_url in site.json, rebuild
and push. Subsequent pushes trigger automatic deployment. A custom domain is optional.

To edit with the wizard, import this source ZIP or site.json into Academic Homepage
Builder. Importing site.json alone requires selecting its attachments again.
Raw resumes and AI input are not included. Original content remains yours.
'''
    return files


def build_project(site: Site, assets: dict[str, bytes], out: Path) -> None:
    out = out.absolute()
    if out.is_symlink():
        raise ValueError('Choose a dedicated build output folder.')
    out = out.resolve()
    if out == Path(out.anchor) or out == Path.home().resolve() or out == Path.cwd().resolve():
        raise ValueError('Choose a dedicated build output folder.')
    if out.exists() and any(out.iterdir()) and not (out / MARKER).is_file():
        raise ValueError('Output contains unrelated files. Choose an empty folder or a previous AHB build.')
    files = public_files(site, assets)
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.ahb-stage-', dir=out.parent) as tmp:
        stage = Path(tmp) / 'site'
        stage.mkdir()
        for name, content in files.items():
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
        check_directory(stage)
        backup = out.parent / ('.ahb-old-' + uuid.uuid4().hex)
        if out.exists():
            out.rename(backup)
        try:
            stage.rename(out)
        except Exception:
            if backup.exists():
                backup.rename(out)
            raise
        if backup.exists():
            # This is the verified former output, renamed within the same parent.
            if backup.resolve().parent != out.parent or backup.is_symlink():
                raise ValueError('Unexpected backup path.')
            shutil.rmtree(backup)


def load_project(project: Path) -> tuple[Site, dict[str, bytes]]:
    source = project if project.is_file() else project / 'site.json'
    root = source.parent.resolve()
    site = public_site(Site.model_validate_json(source.read_bytes()))
    assets = {}
    for name in asset_references(site):
        path = (root / name).resolve()
        if not valid_asset_path(name) or not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > MAX_UPLOAD:
            raise ValueError('A selected attachment is missing, too large or outside the project.')
        assets[name] = path.read_bytes()
    return site, assets


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.ids = [], []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.refs.extend(attrs[k] for k in ('href', 'src') if attrs.get(k))
        if 'id' in attrs:
            self.ids.append(attrs['id'])


def check_directory(folder: Path) -> None:
    folder = folder.resolve()
    if not (folder / 'index.html').is_file():
        raise ValueError('The generated site has no index.html.')
    for path in folder.rglob('*'):
        if path.is_symlink() or not path.resolve().is_relative_to(folder):
            raise ValueError('Generated files must remain inside the output directory.')
        if path.is_file() and path.suffix.lower() in {'.docx', '.env', '.py', '.json', '.txt'} and path.name != 'robots.txt':
            raise ValueError('Unexpected source or private file in static output.')
    for path in folder.rglob('*.html'):
        page = _Page()
        page.feed(path.read_text(encoding='utf8'))
        if len(page.ids) != len(set(page.ids)):
            raise ValueError('Duplicate page anchors.')
        for ref in page.refs:
            url = urlsplit(ref)
            if url.scheme:
                if url.scheme not in {'https', 'mailto'}:
                    raise ValueError('Unsafe link protocol.')
            elif url.netloc:
                raise ValueError('Protocol-relative links are not supported.')
            elif url.path:
                dest = (path.parent / unquote(url.path)).resolve()
                if not dest.is_relative_to(folder) or not dest.is_file():
                    raise ValueError('Missing or unsafe local resource: ' + ref)
            elif url.fragment and unquote(url.fragment) not in page.ids:
                raise ValueError('Broken page anchor.')

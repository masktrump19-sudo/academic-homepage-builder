"""Public attachment privacy and malformed local-request regressions."""
from io import BytesIO
import json

from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject, DecodedStreamObject, DictionaryObject, NameObject,
    NumberObject, TextStringObject,
)
import pytest

from ahb import ai
from ahb.assets import sanitize_attachment
from ahb.exporter import MARKER, build_project, load_project, public_files, source_files
from ahb.models import Entry, blank_site
from ahb.server import create_app


def pdf_with_hidden_content():
    """Visible text plus attachments, annotations, actions, forms and metadata."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    sentinels = []

    def hidden(label):
        value = f'PRIVATE-{label}-AUDIT-SENTINEL'
        sentinels.append(value.encode())
        return TextStringObject(value)

    def stream(data):
        obj = DecodedStreamObject()
        obj.set_data(data)
        return writer._add_object(obj)

    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica'),
                             NameObject('/Metadata'): stream(hidden('FONT-METADATA').encode())})
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    page[NameObject('/Contents')] = stream(b'BT /F1 12 Tf 10 100 Td (Public CV content) Tj ET')
    embedded = DecodedStreamObject()
    embedded.set_data(hidden('EMBEDDED-FILE').encode())
    embedded[NameObject('/Type')] = NameObject('/EmbeddedFile')
    spec = writer._add_object(DictionaryObject({
        NameObject('/Type'): NameObject('/Filespec'),
        NameObject('/F'): hidden('FILENAME'),
        NameObject('/EF'): DictionaryObject({NameObject('/F'): writer._add_object(embedded)})}))
    rect = ArrayObject([NumberObject(x) for x in (0, 0, 10, 10)])
    annotations = []
    for subtype in ('FileAttachment', 'Text', 'Widget', 'Link'):
        annotation = DictionaryObject({
            NameObject('/Type'): NameObject('/Annot'),
            NameObject('/Subtype'): NameObject('/' + subtype),
            NameObject('/Rect'): rect,
            NameObject('/Contents'): hidden(subtype.upper()),
        })
        if subtype == 'FileAttachment':
            annotation[NameObject('/FS')] = spec
        if subtype == 'Widget':
            annotation[NameObject('/V')] = hidden('FORM-VALUE')
        if subtype == 'Link':
            annotation[NameObject('/A')] = DictionaryObject({
                NameObject('/S'): NameObject('/URI'), NameObject('/URI'): hidden('LINK-DESTINATION')})
        annotations.append(writer._add_object(annotation))
    page[NameObject('/Annots')] = ArrayObject(annotations)
    page[NameObject('/AF')] = ArrayObject([spec])
    page[NameObject('/Metadata')] = stream(hidden('PAGE-METADATA').encode())
    page[NameObject('/PieceInfo')] = DictionaryObject({NameObject('/Private'): stream(hidden('APP-DATA').encode())})
    action = DictionaryObject({NameObject('/S'): NameObject('/JavaScript'),
                               NameObject('/JS'): hidden('JAVASCRIPT')})
    page[NameObject('/AA')] = DictionaryObject({NameObject('/O'): writer._add_object(action)})
    writer._root_object[NameObject('/OpenAction')] = writer._add_object(action)
    writer._root_object[NameObject('/Metadata')] = stream(hidden('CATALOG-METADATA').encode())
    writer._root_object[NameObject('/AcroForm')] = DictionaryObject({
        NameObject('/Fields'): ArrayObject([annotations[2]]),
        NameObject('/XFA'): stream(hidden('XFA').encode())})
    writer._root_object[NameObject('/Names')] = DictionaryObject({
        NameObject('/EmbeddedFiles'): DictionaryObject({NameObject('/Names'): ArrayObject([hidden('ATTACHMENT-NAME'), spec])})})
    writer.add_metadata({'/Author': str(hidden('AUTHOR')), '/Title': str(hidden('TITLE'))})
    result = BytesIO()
    writer.write(result)
    return result.getvalue(), sentinels


def test_public_pdf_removes_annotations_hidden_streams_and_metadata():
    original, sentinels = pdf_with_hidden_content()
    assert b'PRIVATE-' in original
    cleaned, suffix, mime = sanitize_attachment('public-cv.pdf', original)
    assert (suffix, mime) == ('.pdf', 'application/pdf')
    reader = PdfReader(BytesIO(cleaned))
    assert len(reader.pages) == 1
    assert 'Public CV content' in reader.pages[0].extract_text()
    assert reader.metadata is None
    for key in ('/AcroForm', '/Metadata', '/Names', '/OpenAction'):
        assert key not in reader.trailer['/Root']
    for key in ('/Annots', '/AA', '/AF', '/Metadata', '/PieceInfo'):
        assert key not in reader.pages[0]
    font = reader.pages[0]['/Resources']['/Font']['/F1'].get_object()
    assert '/Metadata' not in font
    # Check every serialized object, including unreferenced streams that a
    # dictionary-only inspection could miss after deleting a reference.
    all_bytes = cleaned
    for generation, offsets in reader.xref.items():
        for object_id in offsets:
            if object_id == 0:
                continue
            from pypdf.generic import IndirectObject
            obj = reader.get_object(IndirectObject(object_id, generation, reader))
            if hasattr(obj, 'get_data'):
                all_bytes += obj.get_data()
            all_bytes += str(obj).encode()
    assert all(sentinel not in all_bytes for sentinel in sentinels)


@pytest.fixture
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        client.headers['X-AHB-Token'] = client.get('/api/config').json()['token']
        yield client


@pytest.mark.parametrize('endpoint', ['parse-text', 'preview', 'export', 'assist-pack', 'ai'])
@pytest.mark.parametrize('payload', [[], 'private request string', 1, False, None])
def test_json_endpoints_reject_non_object_without_server_error(client, endpoint, payload):
    response = client.post('/api/' + endpoint, content=json.dumps(payload),
                           headers={'Content-Type': 'application/json'})
    assert response.status_code == 422, response.text
    assert 'JSON object' in response.json()['detail']
    assert 'private request string' not in response.text


@pytest.mark.parametrize('endpoint', ['parse-text', 'preview', 'export', 'assist-pack', 'ai'])
def test_invalid_json_returns_clear_error(client, endpoint):
    response = client.post('/api/' + endpoint, content=b'{invalid-private-input',
                           headers={'Content-Type': 'application/json'})
    assert response.status_code == 422
    assert response.json()['detail'] == 'Send a valid JSON object.'


@pytest.mark.parametrize('languages', [[{}], [[]], ['en', {}], [True], [None]])
@pytest.mark.parametrize('endpoint', ['assist-pack', 'ai'])
def test_bad_ai_language_types_never_invoke_provider(client, monkeypatch, endpoint, languages):
    monkeypatch.setattr(ai, 'status', lambda: pytest.fail('Malformed input must not call Codex'))
    response = client.post('/api/' + endpoint,
                           json={'text': 'Fictional draft', 'languages': languages, 'consent': True})
    assert response.status_code == 422, response.text
    assert 'Choose English' in response.json()['detail']


@pytest.mark.parametrize('model', [False, 0, [], {}, ''])
def test_invalid_model_type_never_invokes_provider(monkeypatch, model):
    monkeypatch.setattr(ai, 'status', lambda: pytest.fail('Malformed input must not call Codex'))
    with pytest.raises(ValueError, match='model identifier'):
        ai.generate('Fictional draft', ['en'], model=model)


@pytest.mark.parametrize('kind', [[], {}, 1, None])
def test_bad_export_kind_returns_validation_error(client, kind):
    site = blank_site().model_dump(mode='json')
    response = client.post('/api/export', json={'site': site, 'kind': kind, 'reviewed': True})
    assert response.status_code == 422, response.text
    assert 'static website' in response.json()['detail']


def image_with_metadata(format='JPEG', color='blue'):
    image = Image.new('RGB', (24, 24), color)
    exif = Image.Exif()
    exif[315] = 'PRIVATE-IMAGE-AUTHOR-SENTINEL'
    output = BytesIO()
    image.save(output, format=format, exif=exif)
    return output.getvalue()


@pytest.mark.parametrize('exporter', [public_files, source_files])
def test_every_export_sanitizes_manually_supplied_assets_and_normalizes_images(exporter):
    site = blank_site()
    site.profile.name = {'en': 'Fictional Researcher'}
    site.profile.portrait = 'assets/uploads/photo.jpg'
    site.profile.cv = 'assets/uploads/cv.pdf'
    pdf, sentinels = pdf_with_hidden_content()
    original = site.model_dump(mode='json')
    files = exporter(site, {'assets/uploads/photo.jpg': image_with_metadata(),
                            'assets/uploads/cv.pdf': pdf})
    assert site.model_dump(mode='json') == original
    assert 'assets/uploads/photo.jpg' not in files
    assert 'assets/uploads/photo.png' in files
    with Image.open(BytesIO(files['assets/uploads/photo.png'])) as image:
        assert image.format == 'PNG'
        assert not image.getexif()
    public_data = b''.join(files.values())
    assert b'PRIVATE-IMAGE-AUTHOR-SENTINEL' not in public_data
    assert all(sentinel not in files['assets/uploads/cv.pdf'] for sentinel in sentinels)
    reference = files.get('site.json', files.get('index.html'))
    assert b'assets/uploads/photo.png' in reference
    assert b'assets/uploads/photo.jpg' not in reference


def test_normalized_images_do_not_overwrite_other_selected_images():
    site = blank_site()
    site.profile.name = {'en': 'Fictional Researcher'}
    site.profile.portrait = 'assets/uploads/photo.jpg'
    site.sections['projects'] = [Entry(title={'en': 'Fictional Project'}, confirmed=True,
                                      image='assets/uploads/photo.png')]
    assets = {'assets/uploads/photo.jpg': image_with_metadata(color='red'),
              'assets/uploads/photo.png': image_with_metadata(format='PNG', color='blue')}
    source = source_files(site, assets)
    data = json.loads(source['site.json'])
    portrait_path = data['profile']['portrait']
    project_path = data['sections']['projects'][0]['image']
    assert portrait_path != project_path
    with Image.open(BytesIO(source[portrait_path])) as portrait:
        assert portrait.getpixel((0, 0))[0] > 200
    with Image.open(BytesIO(source[project_path])) as project:
        assert project.getpixel((0, 0))[2] > 200
    static = public_files(site, assets)
    assert portrait_path in static and project_path in static


def test_cli_build_cleans_manual_assets_after_loading(tmp_path):
    site = blank_site()
    site.profile.name = {'en': 'Fictional Researcher'}
    site.profile.portrait = 'assets/uploads/photo.jpg'
    (tmp_path / 'site.json').write_text(site.model_dump_json(), encoding='utf8')
    folder = tmp_path / 'assets/uploads'
    folder.mkdir(parents=True)
    (folder / 'photo.jpg').write_bytes(image_with_metadata())
    loaded, assets = load_project(tmp_path)
    out = tmp_path / 'dist'
    build_project(loaded, assets, out)
    assert (out / 'assets/uploads/photo.png').is_file()
    assert not (out / 'assets/uploads/photo.jpg').exists()
    assert b'PRIVATE-IMAGE-AUTHOR-SENTINEL' not in b''.join(
        file.read_bytes() for file in out.rglob('*') if file.is_file())


def test_output_alias_cannot_replace_current_directory(tmp_path, monkeypatch):
    work = tmp_path / 'workspace'
    work.mkdir()
    (work / MARKER).write_text('A previous build marker does not authorize replacing cwd.')
    (work / 'keep.txt').write_text('Keep this file.')
    monkeypatch.chdir(work)
    site = blank_site()
    site.profile.name = {'en': 'Fictional Researcher'}
    with pytest.raises(ValueError, match='dedicated build output'):
        build_project(site, {}, work / 'unused' / '..')
    assert (work / 'keep.txt').read_text() == 'Keep this file.'

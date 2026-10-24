import json
import zipfile
from io import BytesIO
from pathlib import Path
import subprocess
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from ahb.models import Site, blank_site, Entry
from ahb.exporter import build_project, check_directory, public_files, source_files, make_zip
from ahb.server import create_app
from ahb import ai


def person(name='Demo Person'):
    site = blank_site()
    site.profile.name = {'en': name, 'zh': '演示人物'}
    return site


def png():
    stream = BytesIO()
    Image.new('RGB', (20, 20), '#597b8b').save(stream, 'PNG')
    return stream.getvalue()


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        client.headers['X-AHB-Token'] = client.get('/api/config').json()['token']
        yield client


def test_loopback_csrf_and_no_source_logging(client):
    assert client.post('/api/parse-text', json={'text': 'Demo Person'}, headers={'Origin':'https://hostile.example'}).status_code == 403
    assert client.get('/api/config', headers={'Host':'hostile.example'}).status_code == 403
    assert client.post('/api/parse-text', json={'text':'Demo Person'}, headers={'X-AHB-Token':''}).status_code == 403
    response = client.get('/api/config')
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'


def test_build_does_not_delete_unrelated_folder(tmp_path):
    out = tmp_path/'important'
    out.mkdir()
    (out/'keep.txt').write_text('Keep my data')
    with pytest.raises(ValueError):
        build_project(person(), {}, out)
    assert (out/'keep.txt').read_text() == 'Keep my data'


def test_sequential_builds_remove_previous_person_and_assets(tmp_path):
    first=person('First Confidential Person')
    first.profile.portrait='assets/uploads/first.png'
    out=tmp_path/'site'
    build_project(first, {'assets/uploads/first.png':png()}, out)
    assert (out/'assets/uploads/first.png').exists()
    build_project(person('Second Demo'), {}, out)
    assert not (out/'assets/uploads/first.png').exists()
    assert b'First Confidential Person' not in b''.join(p.read_bytes() for p in out.rglob('*') if p.is_file())
    check_directory(out)


def test_source_omits_disabled_hidden_content():
    site=person()
    site.sections['projects']=[Entry(title={'en':'PRIVATE DISABLED'},enabled=False)]
    site.sections['honors']=[Entry(title={'en':'PRIVATE HIDDEN'},confirmed=False)]
    site.hidden_sections=['honors']
    files=source_files(site,{})
    assert b'PRIVATE DISABLED' not in files['site.json']
    assert b'PRIVATE HIDDEN' not in files['site.json']
    assert 'ahb/server.py' not in files and 'ahb/ai.py' not in files
    assert 'build.py' in files and 'requirements.txt' in files


def test_hidden_language_and_unused_asset_do_not_leak():
    site=person()
    site.languages=['en']
    site.profile.bio={'en':'Public bio','zh':'PRIVATE TRANSLATION SENTINEL'}
    site.hidden_sections=['honors']
    site.sections['honors']=[Entry(title={'en':'Hidden'},image='assets/uploads/hidden.png')]
    files=source_files(site,{'assets/uploads/hidden.png':png()})
    assert b'PRIVATE TRANSLATION SENTINEL' not in files['site.json']
    assert 'assets/uploads/hidden.png' not in files
    assert public_files(site,{})


def test_large_resume_upload_never_rolls_to_disk(client,monkeypatch):
    import tempfile
    def forbidden_rollover(self):
        pytest.fail('Raw resume was written to disk')
    monkeypatch.setattr(tempfile.SpooledTemporaryFile,'rollover',forbidden_rollover)
    response=client.post('/api/parse',files={'file':('resume.txt',b'X'*1500000,'text/plain')})
    assert response.status_code==422  # Text is too long, but was handled entirely in RAM.


def test_unreviewed_entries_cannot_publish_but_can_preview():
    site=person()
    site.sections['projects']=[Entry(title={'en':'Unconfirmed title'})]
    with pytest.raises(ValueError,match='Review'):
        public_files(site,{})
    assert 'index.html' in public_files(site,{},reviewed=False)


def test_attachment_is_explicit_and_session_clear(client):
    site=person()
    result=client.post('/api/assets', files={'file':('photo.jpg',png(),'image/jpeg')})
    assert result.status_code == 200
    asset=result.json()
    assert asset['path'].startswith('assets/uploads/') and 'photo' not in asset['path']
    site.profile.portrait=asset['path']
    response=client.post('/api/export',json={'site':site.model_dump(),'asset_ids':[],'reviewed':True})
    assert response.status_code == 422
    response=client.post('/api/export',json={'site':site.model_dump(),'asset_ids':[asset['id']],'reviewed':True})
    assert response.status_code == 200
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert asset['path'] in archive.namelist()
        assert not any('resume' in name for name in archive.namelist())
    assert client.delete('/api/session').json()['cleared']
    assert client.post('/api/preview',json={'site':site.model_dump(),'asset_ids':[asset['id']]}).status_code==422


def test_import_and_update_public_project_roundtrip(client):
    site=person()
    files=source_files(site,{})
    result=client.post('/api/import', files={'file':('source.zip',make_zip(files),'application/zip')})
    assert result.status_code==200, result.text
    data=result.json()['site']
    data['sections']['projects']=[Entry(title={'en':'A new project'},confirmed=True).model_dump()]
    response=client.post('/api/export',json={'site':data,'reviewed':True,'kind':'source','asset_ids':[]})
    assert response.status_code==200
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert 'A new project' in archive.read('site.json').decode()


def test_import_rejects_zip_traversal(client):
    payload=make_zip({'site.json':person().model_dump_json().encode(),'../outside.txt':b'bad'})
    assert client.post('/api/import',files={'file':('evil.zip',payload,'application/zip')}).status_code==422


def test_reject_svg_active_content_and_url_injection(client):
    assert client.post('/api/assets', files={'file':('attack.svg',b'<svg onload="alert(1)"/>','image/svg+xml')}).status_code==422
    data=person().model_dump()
    data['profile']['links']=[{'label':'Bad','url':'javascript:alert(1)'}]
    assert client.post('/api/preview',json={'site':data,'asset_ids':[]}).status_code==422


def test_private_raw_resume_not_exported(client):
    raw='Demo Person\nPRIVATE SENTINEL phone 12345678901\nEducation\nExample University'
    result=client.post('/api/parse-text',json={'text':raw})
    assert result.status_code==200
    response=client.post('/api/export',json={'site':person().model_dump(),'reviewed':True,'kind':'source','asset_ids':[]})
    assert response.status_code==200
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert b'PRIVATE SENTINEL' not in b''.join(archive.read(n) for n in archive.namelist())


def test_no_network_during_local_preview_and_export(client,monkeypatch):
    import socket
    def deny(*args,**kwargs):
        raise AssertionError('Unexpected outbound network request')
    monkeypatch.setattr(socket,'create_connection',deny)
    assert client.post('/api/parse-text',json={'text':'Alex Morgan\nResearch interests\nGeometry'}).status_code==200
    assert client.post('/api/preview',json={'site':person().model_dump(),'asset_ids':[]}).status_code==200
    assert client.post('/api/export',json={'site':person().model_dump(),'reviewed':True,'asset_ids':[]}).status_code==200


def test_ai_requires_per_request_consent(client,monkeypatch):
    monkeypatch.setattr(ai,'generate',lambda *args: pytest.fail('Must not call Codex without consent'))
    assert client.post('/api/ai',json={'text':'Demo','consent':False}).status_code==422


def test_ai_disabled_when_cli_unavailable(monkeypatch):
    monkeypatch.setattr(ai.shutil,'which',lambda _:None)
    assert ai.status()['ready'] is False
    with pytest.raises(ValueError):
        ai.generate('Demo',['en'])


def test_collaboration_pack_contains_only_selected_text():
    with zipfile.ZipFile(BytesIO(ai.collaboration_pack('SELECTED TEXT',['en']))) as archive:
        assert 'SELECTED TEXT' in archive.read('prompt.txt').decode()
        assert set(archive.namelist())=={'prompt.txt','site.schema.json','README.txt'}


def test_codex_restricted_invocation_and_tentative_result(monkeypatch):
    monkeypatch.setattr(ai,'status',lambda:{'ready':True})
    monkeypatch.setattr(ai.shutil,'which',lambda _:'codex')
    def fake_run(args,**kw):
        assert '--ignore-user-config' in args and '--ephemeral' in args
        assert args[args.index('--sandbox')+1]=='read-only'
        assert '--dangerously-bypass-approvals-and-sandbox' not in args
        assert 'UNTRUSTED SOURCE DATA' in kw['input']
        output=Path(args[args.index('--output-last-message')+1])
        site=person()
        site.sections['projects']=[Entry(title={'en':'Candidate'},confirmed=True)]
        output.write_text(site.model_dump_json(),encoding='utf8')
        return subprocess.CompletedProcess(args,0,'','')
    monkeypatch.setattr(ai,'_run',fake_run)
    result=ai.generate('Demo profile',['en'])
    assert result['site']['sections']['projects'][0]['confirmed'] is False
    assert result['warnings']


@pytest.mark.parametrize('failure',['timeout','error','invalid'])
def test_ai_failure_preserves_callers_draft(monkeypatch,failure):
    monkeypatch.setattr(ai,'status',lambda:{'ready':True})
    monkeypatch.setattr(ai.shutil,'which',lambda _:'codex')
    original=person().model_dump()
    def fake(args,**kw):
        if failure=='timeout':
            raise subprocess.TimeoutExpired(args,180)
        if failure=='invalid':
            Path(args[args.index('--output-last-message')+1]).write_text('not json')
        return subprocess.CompletedProcess(args,1 if failure=='error' else 0,'','PRIVATE PROVIDER MESSAGE')
    monkeypatch.setattr(ai,'_run',fake)
    with pytest.raises(ValueError) as exc:
        ai.generate('Demo',['en'])
    assert 'PRIVATE PROVIDER MESSAGE' not in str(exc.value)
    assert original==person().model_dump()

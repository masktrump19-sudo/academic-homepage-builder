from pathlib import Path

import pytest

from ahb.exporter import check_directory
from scripts.build_demo import MARKER, NOINDEX, build_demo, gallery_files


def test_gallery_has_three_bilingual_offline_templates(tmp_path):
    output = build_demo(tmp_path / 'gallery')
    check_directory(output)
    assert (output / 'index.html').is_file()
    for template in ('academic', 'modern', 'visual'):
        for page in ('index.html', 'zh/index.html'):
            html = (output / template / page).read_text(encoding='utf8')
            assert f'data-template="{template}"' in html
            assert NOINDEX in html
            assert 'Fictional demo' in html or '虚构演示' in html
            assert 'rel="canonical"' not in html
        assert (output / template / 'assets/site.css').is_file()
        assert (output / template / 'assets/site.js').is_file()
        assert not (output / template / 'sitemap.xml').exists()
    assert NOINDEX in (output / 'index.html').read_text(encoding='utf8')
    assert 'Disallow: /' in (output / 'robots.txt').read_text()
    assert 'noindex' in (output / '_headers').read_text()
    assert not list(output.rglob('*.json'))
    assert not list(output.rglob('uploads'))


def test_demo_build_is_fresh_and_preserves_unrelated_folders(tmp_path):
    output = build_demo(tmp_path / 'gallery')
    (output / 'stale-private.html').write_text('old build content')
    build_demo(output)
    assert not (output / 'stale-private.html').exists()
    assert (output / MARKER).exists()
    other = tmp_path / 'unrelated'
    other.mkdir()
    important = other / 'notes.html'
    important.write_text('Do not remove')
    with pytest.raises(ValueError, match='unrelated'):
        build_demo(other)
    assert important.read_text() == 'Do not remove'


def test_demo_uses_no_network_dependencies_or_source_content():
    files = gallery_files()
    assert len([name for name in files if name.endswith('.html')]) == 7
    for name, raw in files.items():
        content = raw.decode()
        if name.endswith('.html'):
            assert 'src="https:' not in content
            assert 'src="http:' not in content
        if name.endswith('.css'):
            assert '@import' not in content
            assert 'https://' not in content
        assert 'site.json' not in name
        assert 'resume' not in name

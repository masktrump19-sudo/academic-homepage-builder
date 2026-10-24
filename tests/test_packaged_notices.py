"""Installed packages and standalone exports retain the required notices."""
from pathlib import Path
import shutil

import pytest

from ahb import exporter
from ahb.models import blank_site


ROOT = Path(__file__).resolve().parents[1]
NOTICES = ('LICENSE', 'THIRD_PARTY_NOTICES.md')


def fictional_site():
    site = blank_site()
    site.profile.name = {'en': 'Fictional Researcher'}
    return site


def test_packaged_notices_match_repository_notices():
    for name in NOTICES:
        assert (ROOT / 'ahb/licenses' / name).read_bytes() == (ROOT / name).read_bytes()


def test_export_from_installed_package_uses_own_notices(tmp_path, monkeypatch):
    package = tmp_path / 'site-packages/ahb'
    shutil.copytree(ROOT / 'ahb', package, ignore=shutil.ignore_patterns('__pycache__'))
    # A license at the site-packages root belongs to no particular package.
    # The builder must use its bundled notices instead of that unrelated file.
    (package.parent / 'LICENSE').write_text('UNRELATED DISTRIBUTION LICENSE')
    monkeypatch.setattr(exporter, '__file__', str(package / 'exporter.py'))
    files = exporter.source_files(fictional_site(), {})
    for name in NOTICES:
        assert files[name] == (ROOT / name).read_bytes()


def test_reexport_standalone_source_keeps_root_notices(tmp_path, monkeypatch):
    first = exporter.source_files(fictional_site(), {})
    for name, data in first.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    assert not (tmp_path / 'ahb/licenses').exists()
    monkeypatch.setattr(exporter, '__file__', str(tmp_path / 'ahb/exporter.py'))
    second = exporter.source_files(fictional_site(), {})
    for name in NOTICES:
        assert second[name] == first[name]


def test_incomplete_install_fails_instead_of_dropping_license(tmp_path, monkeypatch):
    package = tmp_path / 'ahb'
    shutil.copytree(ROOT / 'ahb', package, ignore=shutil.ignore_patterns('__pycache__', 'licenses'))
    monkeypatch.setattr(exporter, '__file__', str(package / 'exporter.py'))
    with pytest.raises(ValueError, match='Required license notice is missing'):
        exporter.source_files(fictional_site(), {})

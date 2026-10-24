from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from scripts.privacy_audit import inspect_file


@pytest.mark.parametrize('extension', ['zip', 'whl'])
def test_release_archives_are_scanned_after_decompression(tmp_path, extension):
    archive = tmp_path / ('release.' + extension)
    marker = 'PRIVATE_FIXTURE_MARKER_NOT_FOR_PUBLIC_EXPORT'
    with ZipFile(archive, 'w', ZIP_DEFLATED) as output:
        output.writestr('ahb/fixture.txt', marker)
    count, findings = inspect_file(archive, archive.name, [marker.casefold()], False)
    assert count == 1
    assert findings
    assert all('ahb/fixture.txt' in path for path, _ in findings)

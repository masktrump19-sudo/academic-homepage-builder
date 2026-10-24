"""Audit publishable files without printing sensitive matching values.

Use --deny-file with a JSON array stored outside the repository for a private,
owner-specific release check. This script does not upload data anywhere.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_ZIP_BYTES = 128 * 1024 * 1024
MAX_ZIP_MEMBERS = 1500
SKIP_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache',
    '.ruff_cache', '.ahb-work', 'node_modules', 'build', 'dist', 'private',
    'test-results', 'playwright-report',
}
PRIVATE_PARTS = {'private', 'research', 'raw-resumes', 'raw_resume', 'raw-resume'}
SENSITIVE_PATTERNS = [
    ('private-key', re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('github-token', re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b')),
    ('github-fine-grained-token', re.compile(rb'\bgithub_pat_[A-Za-z0-9_]{50,}\b')),
    ('api-key', re.compile(rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}\b')),
    ('cloud-access-key', re.compile(rb'\bAKIA[A-Z0-9]{16}\b')),
]
EMAIL = re.compile(r'(?<![\w.+-])[A-Za-z0-9][A-Za-z0-9._+%-]*@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)')
EXAMPLE_DOMAINS = {'example.com', 'example.org', 'example.net', 'example.edu', 'localhost.localdomain'}
USER_PATH = re.compile(r'(?:[A-Za-z]:[\\/]+Users[\\/]+[^\s\\/<>"\x00]+|' + '/' + r'(?:Users|home)/[^\s/<>"\x00]+)')


def ignored(path: Path) -> bool:
    return any(part in SKIP_DIRS or part.endswith('.egg-info') for part in path.parts)


def candidate_files(root: Path) -> list[Path]:
    """Use Git's ignore rules when possible; otherwise use safe local exclusions."""
    try:
        result = subprocess.run(
            ['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
            capture_output=True, timeout=10, check=True,
        )
        git_root = Path(result.stdout.decode('utf-8').strip()).resolve()
        if git_root == root:
            listing = subprocess.run(
                ['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                capture_output=True, timeout=15, check=True,
            )
            return sorted({root / name for name in listing.stdout.decode('utf-8').split('\0') if name})
    except (OSError, subprocess.SubprocessError, UnicodeError):
        pass
    return sorted(p for p in root.rglob('*') if p.is_file() and not ignored(p.relative_to(root)))


def load_deny_list(path: Path | None) -> list[str]:
    if path is None:
        return []
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, list) or any(not isinstance(item, str) or len(item.strip()) < 3 for item in value):
        raise ValueError('Deny file must be a JSON array of strings, each at least 3 characters.')
    return [item.casefold() for item in value]


def inspect_git_metadata(root: Path, deny: list[str]) -> list[tuple[str, str]]:
    """Check names/emails/messages in locally available commits; never print values."""
    try:
        probe = subprocess.run(
            ['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
            capture_output=True, timeout=10, check=True,
        )
        if Path(probe.stdout.decode('utf-8').strip()).resolve() != root:
            return []
        log = subprocess.run(
            ['git', '-C', str(root), 'log', '--all', '--format=%an%n%ae%n%cn%n%ce%n%B'],
            capture_output=True, timeout=20,
        )
        if log.returncode:
            # An initialized repository without a first commit is normal.
            head = subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify', 'HEAD'], capture_output=True, timeout=10)
            return [] if head.returncode else [('Git commit metadata', 'metadata-could-not-be-read')]
        return inspect_bytes('Git commit metadata', log.stdout, deny, False)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return []


def readable_text(data: bytes) -> str:
    text = data.decode('utf-8', errors='ignore')
    # Inspect common escaped Unicode without interpreting arbitrary escape syntax.
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        text += '\n' + data.decode('utf-16', errors='ignore')
    return text


def inspect_bytes(label: str, data: bytes, deny: list[str], allow_emails: bool) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    normalized = label.replace('\\', '/')
    member_name = normalized.split('!', 1)[-1]
    path = PurePosixPath(member_name)
    if path.is_absolute() or '..' in path.parts or re.match(r'^[A-Za-z]:', member_name):
        issues.append((label, 'unsafe-archive-path'))
    if any(part.casefold() in PRIVATE_PARTS for part in path.parts):
        issues.append((label, 'private-artifact-path'))
    if path.name.startswith('.env') or path.name in {'auth.json', 'credentials.json', 'cookies.json'}:
        issues.append((label, 'credential-artifact-path'))
    if path.name.startswith('preview-'):
        issues.append((label, 'unreviewed-preview-artifact'))
    if len(data) > MAX_FILE_BYTES:
        return issues + [(label, 'file-too-large-to-audit')]
    for rule, regex in SENSITIVE_PATTERNS:
        if regex.search(data):
            issues.append((label, rule))
    raw_text = readable_text(data)
    text = raw_text
    if path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.tiff'}:
        # Compressed pixel bytes can coincidentally resemble short emails. Scan
        # image text metadata instead; retain raw-byte deny/credential matching.
        text = ''
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                metadata = image.getexif()
                if any(key != 274 for key in metadata):
                    issues.append((label, 'image-exif-metadata'))
                values = [value for value in image.info.values() if isinstance(value, str)]
                values.extend(value for value in metadata.values() if isinstance(value, str))
                for key in ('comment', 'xmp', 'XML:com.adobe.xmp'):
                    value = image.info.get(key)
                    if isinstance(value, bytes):
                        values.append(readable_text(value))
                text = '\n'.join(values)
        except ImportError:
            issues.append((label, 'image-metadata-not-inspected-install-pillow'))
        except Exception:
            issues.append((label, 'unreadable-image'))
    folded = (normalized + '\n' + raw_text + '\n' + text).casefold()
    if any(marker in folded for marker in deny):
        issues.append((label, 'private-deny-list-match'))
    if USER_PATH.search(text):
        # Do not output the matched username or private path.
        issues.append((label, 'absolute-user-home-path'))
    if not allow_emails:
        for match in EMAIL.finditer(text):
            domain = match.group(1).lower()
            if domain in EXAMPLE_DOMAINS or domain.endswith(('.example', '.test', '.invalid', '.example.org', '.example.com', '.example.net')):
                continue
            if domain == 'users.noreply.github.com':
                continue
            issues.append((label, 'non-example-email'))
            break
    return issues


def inspect_file(path: Path, label: str, deny: list[str], allow_emails: bool) -> tuple[int, list[tuple[str, str]]]:
    if path.is_symlink():
        return 1, [(label, 'symlink-not-audited')]
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return 1, [(label, 'file-too-large-to-audit')]
        data = path.read_bytes()
    except OSError:
        return 1, [(label, 'file-could-not-be-read')]
    if path.suffix.lower() != '.zip':
        return 1, inspect_bytes(label, data, deny, allow_emails)
    issues = inspect_bytes(label, b'', deny, allow_emails)
    count = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ZIP_MEMBERS or sum(m.file_size for m in members) > MAX_ZIP_BYTES:
                return 1, issues + [(label, 'archive-too-large-to-audit')]
            seen = set()
            for member in members:
                if member.is_dir():
                    continue
                member_label = f'{label}!{member.filename}'
                if member.filename in seen:
                    issues.append((member_label, 'duplicate-archive-member'))
                seen.add(member.filename)
                if member.flag_bits & 1 or member.file_size > MAX_FILE_BYTES:
                    issues.append((member_label, 'encrypted-or-large-archive-member'))
                    continue
                if member.filename.lower().endswith('.zip'):
                    issues.append((member_label, 'nested-archive-needs-separate-audit'))
                    continue
                # ZIP members are read in memory and are never extracted.
                count += 1
                issues.extend(inspect_bytes(member_label, archive.read(member), deny, allow_emails))
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError):
        issues.append((label, 'archive-could-not-be-inspected'))
    return count, issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', nargs='?', default='.', help='Repository, directory, file, or ZIP to inspect')
    parser.add_argument('--deny-file', type=Path, help='Private JSON list of forbidden strings; keep outside the repository')
    parser.add_argument('--allow-contact-emails', action='store_true', help='For reviewed personal-site exports only; still enforce deny list and credential checks')
    args = parser.parse_args(argv)
    target = Path(args.target).resolve()
    try:
        deny = load_deny_list(args.deny_file)
    except (OSError, ValueError, json.JSONDecodeError):
        print('Privacy audit could not read a valid deny list. Contents were not printed.', file=sys.stderr)
        return 2
    if not target.exists():
        print('Privacy audit target does not exist.', file=sys.stderr)
        return 2
    paths = candidate_files(target) if target.is_dir() else [target]
    issues: list[tuple[str, str]] = []
    checked = 0
    for path in paths:
        label = path.relative_to(target).as_posix() if target.is_dir() else path.name
        count, found = inspect_file(path, label, deny, args.allow_contact_emails)
        checked += count
        issues.extend(found)
    if target.is_dir():
        issues.extend(inspect_git_metadata(target, deny))
    for path, rule in sorted(set(issues)):
        for marker in deny:
            path = re.sub(re.escape(marker), '<redacted>', path, flags=re.I)
        print(f'FAIL [{rule}] {path}')
    if issues:
        print(f'Privacy audit failed: {len(set(issues))} finding(s), {checked} file(s) inspected. Matching values were not printed.')
        return 1
    print(f'Privacy audit passed: {checked} file(s) inspected. Review visible image/document content and historical binary assets separately.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

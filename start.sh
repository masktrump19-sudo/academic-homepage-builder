#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
if ! .venv/bin/python -c 'import ahb, fastapi, pypdf, docx, PIL' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements.txt -e .
fi
exec .venv/bin/python -m ahb serve

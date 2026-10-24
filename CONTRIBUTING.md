# Contributing

Small, reviewable changes are welcome: better import accuracy, accessibility,
templates, translations, and deployment guidance.

1. Open an issue describing the problem, using fictional or fully redacted data.
2. Create a branch and implement the smallest useful change.
3. Install `python -m pip install -r requirements.txt`, then `python -m pip install -e ".[test]"`, and run `python -m pytest`.
4. Run `python scripts/privacy_audit.py .` and check the actual diff before opening a PR.

For template changes, check English and Chinese, long titles, empty sections,
mobile widths, and light/dark themes. Attach screenshots using only the fictional
demo. Do not paste a real résumé or a person's contact details into an issue.

Keep the local-first boundary: ordinary import, editing, preview, and export must
not call external services. Any new network-dependent feature must be explicit,
optional, and documented before data leaves the device.

Treat imported documents and model output as untrusted input. Preserve review
steps and fail safely when data cannot be understood; do not silently turn an
unreviewed draft into a published claim.

Use your GitHub noreply commit email. The current privacy CI rejects personal
email addresses in commit metadata, so noreply is required for contributions.
Review the contributor name in your local Git settings before committing.
By contributing, you agree to license your contribution under the project's MIT
license. Security reports belong in the private process in [SECURITY.md](SECURITY.md).

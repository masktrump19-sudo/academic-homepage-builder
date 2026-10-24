# Release checks

Run tests and inspect the real release files before publishing. Do not point the
release at a working folder containing a real person's original materials.

```sh
python -m pytest
python scripts/privacy_audit.py .
python scripts/privacy_audit.py path/to/export.zip
```

To audit for specific personal information, create a JSON array of sensitive
strings **outside this repository** and pass its absolute path:

```sh
python scripts/privacy_audit.py . --deny-file /private/location/deny-list.json
```

Do not publish that deny-list: its entries are themselves private data. The scanner
reports rule names and file paths without printing matched secrets. It also scans
ZIP members, common credential shapes, personal email addresses outside reserved
example domains, absolute user-home paths, and source artifacts that should not ship.
It also checks author/committer names, emails, and messages in the locally available
Git commits. Use a full checkout for release review: a shallow CI checkout does not
contain older history. Review historical binary assets separately. The exit code
is nonzero when it finds a problem or cannot safely inspect a file.

Review actual images and documents separately. A metadata/string scan does not
prove that a screenshot, face, QR code, or rendered PDF contains no private information.

## Release acceptance

- Test a minimal profile with no publications or social links, plus long bilingual content.
- Verify all three templates at mobile and desktop widths in light and dark themes.
- Import and re-export a source project, then update a paper/project without rebuilding from scratch.
- Reject unsafe links, traversal paths, malformed uploads, and unreviewed entries.
- Confirm a second person's export contains no assets or text from the first project.
- Confirm the ordinary local flow has no external network requests.
- Exercise Codex unavailable, timeout, malformed output, and unconfirmed results.
- Deploy only the fictional demo, verify the actual public URL, then push one real demo change
  and verify Git integration updates the deployment.
- Audit repository files, intended ZIPs, screenshots, and Git author/committer metadata.
- Publish a tagged version only after distinguishing completed checks from unresolved limitations.

Keep private release evidence outside the public repository. Public release notes
may include aggregate test results and fictional screenshots, not local account
names, private file paths, raw provider logs, or authentication data.

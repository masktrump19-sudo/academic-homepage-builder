# Validation record

This records checks completed during preparation of version 0.1.0 on
2026-10-24. It separates executable checks from browser and hosting acceptance;
the existence of a CI workflow is not evidence that every hosted runner passed.
All test profiles and AI smoke-test text are fictional.

## Completed local checks

| Check | Evidence and scope |
| --- | --- |
| Automated tests | 131 tests passed locally with Python 3.12 at this checkpoint. Parameterized cases cover the three templates, English/Chinese/bilingual output, missing sections, multiple entries, unsafe content and installed-package licenses. |
| Import failures | Text PDF, DOCX and TXT cases; scanned, encrypted, corrupt, oversized and unsafe archive inputs; extracted candidates remain unconfirmed. |
| Public-content boundary | Hidden sections, disabled languages, unselected or unused assets, and raw résumé text are excluded from exports. A second build removes the first fictional person's content and attachments. |
| Local service | Loopback host and origin checks, per-session request token, explicit attachment approval, session clearing, and bounded uploads that remain in memory. |
| Local network boundary | Automated local preview/export tests deny outbound networking. The browser walkthrough loaded only same-origin scripts, styles and previews; the local server enforces same-origin connections through Content Security Policy. This is not a packet capture of unrelated browser background activity. |
| Optional AI | Consent, unavailable CLI, restricted arguments, timeout, provider errors and invalid JSON paths are tested. Provider diagnostics are not exposed, and successful output remains a tentative draft. Full browser checks of draft preservation remain below. |
| Real Codex smoke test | The installed official client processed deliberately submitted fictional text and returned a valid, unconfirmed draft. This verifies that local installation and account only; other CLI versions and accounts can differ. |
| Independent source build | An exported source package was installed in a separate virtual environment and built successfully using its own included modules and requirements. |
| Browser walkthrough | Pasted a fictional resume, reviewed extracted fields, exported a source ZIP and reopened it in a new session. Independently uploaded, assigned and approved a neutral test avatar. Restored entries correctly required review. |
| Responsive templates | Inspected all three layouts at 1440px desktop and 390px mobile viewports, language switching and dark themes. Document width did not exceed viewport width. No browser console errors appeared in the wizard walkthrough. |
| PDF privacy | Public PDFs are rebuilt without annotations, embedded files, forms, JavaScript, metadata or hidden attachments. Regression fixtures retain visible CV text and verify private markers do not survive in serialized objects or decoded streams. |
| Privacy tooling | Repository candidates and screenshot metadata scanned. Synthetic tests cover private emails, Git noreply identities, external deny lists, unsafe ZIP members and image text metadata. Visible images still need human review. |

## Reproduce the automated checks

Create and activate a Python 3.12 virtual environment, then run:

```sh
python -m pip install -r requirements.txt
python -m pip install -e ".[test]"
python -m pytest
python scripts/privacy_audit.py .
```

The initial public commit passed the GitHub workflow on Windows, macOS and Ubuntu:
[workflow run 40083261050](https://github.com/masktrump19-sudo/academic-homepage-builder/actions/runs/40083261050).
Later release commits require their own successful workflow run.

To reproduce the standalone build, export a reviewed fictional source project,
extract it into a fresh directory, and create a separate virtual environment there:

```sh
python -m pip install -r requirements.txt
python build.py
python -m http.server 8000 --directory dist --bind 127.0.0.1
```

Inspect the generated site locally. Do not copy original résumés or account
credentials into that directory. To repeat the optional AI smoke test, follow
[the Codex guide](codex.md), submit a short fictional profile, and verify that
the result is still unconfirmed before accepting it. Ordinary tests mock AI
responses and do not send their fixtures to an external provider.

## Still pending at this checkpoint

- Actual GitHub + Cloudflare Pages Git-integration deployment of the fictional
  demo, followed by a source change and confirmation of the automatic update.
- Final release ZIP, screenshot, repository-history and hosted CI review.

Update this section with observed results before calling the release fully
accepted. A successful build alone does not prove hosting, appearance, search
indexing, or compatibility with every future provider version.

## 中文说明

当前检查点已完成 131 项本地自动化测试、独立源码环境构建、使用虚构文字的官方
Codex 实际调用，以及浏览器导入、编辑、预览、源码导出与重新打开。三模板桌面、
手机与深浅色已实际查看，PDF 隐藏附件也有专门回归测试。首个公开提交的三平台
CI 已通过；Cloudflare 真实部署与推送自动更新，以及最终公开包检查，仍需以实际
执行结果补充；不能把“已配置 CI”当作所有系统都已验证通过。

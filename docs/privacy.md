# Privacy and data flow

The application has no account database, analytics, telemetry endpoint, or résumé
storage service operated by the project authors.

| Action | What stays local | What can leave the computer |
| --- | --- | --- |
| Import, edit, preview | Original input, extracted text, candidate fields, temporary assets | Nothing through the normal workflow |
| Export | ZIP is downloaded to your device | Nothing until you share or upload it |
| Optional Codex | Local client and its existing credentials | Only the text you approve for the AI request, through your Codex account |
| Collaboration pack | Prepared text, instructions, schema | Whatever you choose to send to your own AI service |
| Deployment | Your local source copy | Confirmed website content and selected files uploaded to your chosen provider |

Dependency installation and any explicit platform or documentation links need
internet access. Those actions are separate from local résumé processing.

## Public content is an explicit choice

The résumé you import is not automatically a public CV attachment. Select an
attachment separately if you want visitors to download it. Inspect PDFs yourself:
the builder does not redact private details inside an intentionally public PDF.

Review candidate fields before export. Do not publish home addresses, identification
numbers, private phone numbers, references' contact details, or internal project
information merely because they appeared in a résumé.

AI suggestions are unconfirmed drafts. Translations can change meaning; publication
status, author order, dates, and academic claims require your review. Imported documents
and model output are data, never instructions to run commands or upload files.

## Local sessions and exported projects

Temporary import data and assets are held for the local session. Clear the session
or stop the application when finished. This does not delete files you downloaded,
original documents, browser-managed downloads, operating-system backups, or any
independent history maintained by an AI provider.

The source export is designed to be deployable: it includes confirmed content,
selected public assets, and build files. It omits the raw résumé, extraction source,
AI prompts, account credentials, and private local notes. Treat any source ZIP you
share as public data and review its contents first.

Each build starts in a fresh output directory. A new project must not inherit
another person's files from a previous build. Existing unrelated output folders
are not silently deleted.

## What this project does not promise

- Local processing does not make your operating system, browser, or an installed
  third-party client anonymous or free from their own logging behavior.
- Optional cloud AI is not offline. The service's account terms and data policy apply.
- Public repositories are associated with their owners' GitHub accounts.
- A scanner cannot reliably recognize every person or private detail in an image.

The bundled demos use fictional content. No original user's CV, profile image,
institution logo, manuscript figure, account token, or personal operation log is
included in the open-source project.

## 中文说明

默认导入、编辑、预览和导出都在本机完成，不上传到项目作者的服务。AI 默认关闭；
启用时会先让你核对要发送的文本，通过你自己的 Codex／ChatGPT 账号处理。

导入简历不等于公开简历。只有你单独选择并确认的公开附件才进入导出包。
公开 PDF 内部的个人信息需要本人检查，工具不会替你自动脱敏。
源码包也包含将要公开的内容，分享前请检查。清空会话不会删除已经下载的 ZIP 或原始文件。

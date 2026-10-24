# Optional Codex and ChatGPT assistance

AI is optional. Importing, reviewing, designing, building, and exporting a site
work without an AI account.

## Use the Codex button

1. Install the **official Codex CLI** using OpenAI's current installation guidance.
2. Sign in using `codex login`. Complete the official browser flow yourself.
3. Run `codex login status` if you need to confirm the authentication method.
4. In the builder, choose the text to send and remove anything unnecessary.
5. Review the disclosure and explicitly start the AI request.
6. Inspect the returned draft in the editor. Confirm facts and translations before exporting.

The adapter does not read or copy `auth.json`, passwords, cookies, tokens, or API
keys. The official client manages its own authentication. ChatGPT subscription
access and API-key billing are different; the builder does not provide access,
guarantee included usage, or bypass account limits.

The adapter runs in a temporary workspace with structured output and restricted
configuration. It is for extracting and editing website content, not for browsing
your folders or deploying your account. Unsupported client capabilities, login
problems, quota limits, or invalid responses leave the existing form intact.
Do not weaken permissions to work around an adapter error.

## Use a collaboration pack instead

Export the selected text and instructions as a collaboration pack. Review its
contents, then supply the pack to your own ChatGPT or Codex session. Ask for a
JSON result conforming to the included structure, download or copy the result,
and import it into the wizard. You can remove sensitive sections before sharing.

This method works independently of the automatic adapter. The exported pack
contains the text you selected and is therefore private until you choose to share it;
do not commit it into a public website repository.

Neither workflow should invent a paper, acceptance, affiliation, date, author order,
or translation of a person's name. Leave unknown details blank and confirm them later.

## 中文说明

- 基础生成不依赖模型。可选按钮使用本机的官方 Codex CLI，登录由官方客户端处理。
- 点击前查看真正要发送的文字；仅上传完成任务所需的内容。
- ChatGPT 订阅与 API 计费是两回事，是否可用以及额度多少以本人账号为准。
- 未安装、未登录、额度不足或返回无效 JSON 时，可手动填写或使用协作包。
- 协作包由你自行交给 ChatGPT／Codex，再导回结果；不要把它当成公开网站素材提交。
- AI 生成的简介、翻译与字段都要核对，不能把“审稿中”自动改成“已发表”。

Official sources: [authentication](https://learn.chatgpt.com/docs/auth),
[Codex CLI](https://developers.openai.com/codex/cli/),
[non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).

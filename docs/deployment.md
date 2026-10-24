# Deploy with GitHub and Cloudflare Pages

[中文步骤](#中文步骤) · [Back to README](../README.md)

The recommended path keeps your source in **your own GitHub repository** and
uses **Cloudflare Pages Git integration**. Creating an account, accepting service
terms, and approving repository access are actions for you to complete.

## 1. Review and export the source project

In the local wizard, inspect every language and the public asset list. Export
the **source project**, then extract it into a new directory. Do not upload the
folder containing your original résumé. The source project includes the confirmed
site content and selected public assets, so treat the entire export as shareable.

To test this export locally:

```sh
python -m pip install -r requirements.txt
python build.py
```

The generated site is in `dist`. Keep the source project for future updates.

## 2. Create a repository you control

On GitHub, create a new repository. **Private is the suggested default** for your
homepage source; a public site does not require publishing its source repository.
Upload or push the extracted source project at the repository root.

If using Git locally, review the file list and your commit identity before the
first push. Do not commit the original résumé, API keys, browser sessions, private
notes, or the AI collaboration pack. Use your own GitHub noreply email if desired.

## 3. Connect Cloudflare Pages

In Cloudflare's Workers & Pages area, choose the Pages flow to **connect/import an
existing Git repository**. Select GitHub, authorize only the required repository,
and choose your new source repository.

| Setting | Value |
| --- | --- |
| Production branch | Your main branch, usually `main` |
| Framework preset | None |
| Root directory | Repository root |
| Build command | `pip install -r requirements.txt && python build.py` |
| Build output directory | `dist` |
| Python version | `3.12` (or a compatible newer supported version) |

Follow the platform's current Python-version setting if its default differs.
Give the Pages project a name and start deployment. Confirm both a successful
build and that the resulting HTTPS page displays your actual content.

Cloudflare provides a `*.pages.dev` address. You do not need to buy a separate
domain. Use the **actual address returned by Cloudflare**, not a guessed candidate:
availability and possible suffixes are determined by the platform.

## 4. Set the final website URL

Once the real address is known, import the source project back into the wizard,
set the website URL to the final HTTPS origin, and export again. Push the updated
source. This generates canonical links, language alternatives, `robots.txt`, and
`sitemap.xml` for the correct host. The initial build can work before this URL is set.

For each later change, update the project in the wizard, review, export, and push.
Git integration triggers another build. Verify the deployment result and keep
your source ZIP or repository as the editable copy.

## Custom domains and search

You may add your own domain from the Pages project's custom-domain settings.
Complete the platform's domain association before making its requested DNS changes.
Buying a domain, renewal fees, DNS ownership verification, and provider account
access remain your responsibility. Platform free tiers are not a promise of
permanent free service.

Search Console ownership verification and indexing requests are optional follow-up
steps. A working public URL or a sitemap does not guarantee Google indexing or ranking.
Do not copy someone else's verification token into your site.

## Why not drag and drop by default?

Cloudflare's drag-and-drop and Wrangler Direct Upload use a different project
path. A Direct Upload project cannot later be switched into native Git integration;
you would need a new project or your own CI workflow. Exported static ZIPs remain
useful for other hosts, but choose the Git flow above for the simplest ongoing updates.

Official references: [Git integration](https://developers.cloudflare.com/pages/get-started/git-integration/),
[Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/),
[custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/),
[build configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/).

## 中文步骤

1. 在本地向导核对全部内容和附件，导出**源码包**，解压到一个新目录。不要上传存放原始简历的目录。
2. 在自己的 GitHub 账号下新建仓库，默认建议私有，把源码包内容放到仓库根目录。
3. 在 Cloudflare Pages 选择连接已有 Git 仓库，只授权这个仓库。构建命令填
   `pip install -r requirements.txt && python build.py`，输出目录填 `dist`，使用 Python 3.12 或兼容版本。
4. 创建项目后，以平台返回的真实 `*.pages.dev` 地址为准，确认部署成功且页面可访问。
5. 把该地址填回向导的站点网址，重新导出并推送，使 canonical、语言链接和站点地图使用真实域名。
6. 以后更新论文、项目或经历，继续修改同一份资料并推送，Git 集成会自动重新构建。

平台登录、仓库授权、协议和域名购买由本人操作。公开网站不要求公开源码仓库。
默认不要选择“拖拽上传”，因为该项目类型不能直接改成 Git 集成。搜索引擎收录需要另外跟进，
生成器不保证收录时间或搜索排名。

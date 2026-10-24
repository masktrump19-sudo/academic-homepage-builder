# Security policy

## Report privately

Please use the repository's **Security → Report a vulnerability** option when
available. If private reporting is unavailable, open an issue requesting a private
contact channel without exploit details or personal data. Do not upload a real
CV, identity document, token, or credential to an issue or pull request.

Include the version, operating system, a minimal fictional reproduction, and
the expected and observed behavior. Redact local usernames and file paths.

## Intended environment

The wizard is a single-user local application bound to `127.0.0.1`. It is not a
multi-user server and must not be exposed through a public tunnel or reverse proxy.
Do not disable the request token or same-origin checks to make it public.

Imported files, links, and AI-generated data are untrusted. Keep dependencies
updated and only upload files you intend to process. A local application still
runs with the operating-system permissions of the user who launches it.

Optional Codex assistance sends the user-approved text through their configured
official client. Never enable broader execution privileges to work around an
unsupported adapter; use the collaboration pack or manual editing instead.

The current release line receives fixes on the default branch. There is no
guaranteed response-time service or third-party account recovery support.

# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities)
for this repository. Include a minimal reproduction and the affected version.

## Credentials

- Never commit a real DeepSeek API key. The application keeps the key in memory only and masks it in
  logs, reports and `run_manifest.json`.
- `.env.example` contains placeholders only. Do not turn it into a real `.env` and commit it.
- If a key is accidentally exposed, revoke it immediately at the
  [DeepSeek platform](https://platform.deepseek.com/api_keys) and rotate it.

## Execution model

SpaceCode Agent writes files into a user-selected workspace and can run a small set of predefined test
commands (`node --test`, `npm test`, `pytest`), each requiring explicit approval. It is **not** an
operating-system sandbox.

- Do not run generated projects with administrator privileges.
- Review generated `package.json` scripts and test files before executing them.
- Command execution is disabled by default; keep it disabled unless you trust the generated project.

## Supported versions

| Version | Supported |
|---|---|
| 1.x | Yes |

## Scope

The built-in demo project is a teaching sample. Its development tokens/passwords are placeholders and
must be replaced in any real deployment.

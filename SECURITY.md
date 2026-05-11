# Security Policy

## Supported Versions

Security fixes are applied to the latest release only.

| Version | Supported |
|---|---|
| 1.1.x | ✅ Yes |
| 1.0.x | ❌ No |

---

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately via [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) on this repository.

Alternatively, you can email the maintainers directly. Include the word **SECURITY** in the subject line.

### What to include

- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- Any suggested mitigations if you have them

### What to expect

- **Acknowledgement** within 72 hours
- **Status update** within 7 days (confirmed, investigating, or not applicable)
- **Coordinated disclosure** — we will work with you on timing before any public disclosure

---

## Security Considerations for Operators

Marrow is designed to run as a **local or private network service**. Before deploying:

- **Do not expose `marrow_server` to the public internet** without authentication. The MCP endpoint has no built-in auth by default — use the optional OAuth router or place it behind a reverse proxy with auth.
- **`PROJECTS_ROOT`** contains all your project artifacts. Ensure filesystem permissions restrict access appropriately.
- **LanceDB data directory** contains vector embeddings of your source code. Treat it as sensitive.
- **`.env` files** must never be committed to version control. The `.gitignore` excludes them by default.
- The worker has read access to all `WATCH_PATHS` — scope these to only the directories you intend to index.

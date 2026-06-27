# Security Policy

coyodex is **alpha (v0.1.0)** software. We take security reports seriously, but
please note there is no formal support contract or guaranteed response time yet.

## Supported versions

Only the latest version on the `main` branch is supported. There are no
backported fixes for older versions during alpha.

| Version      | Supported          |
| ------------ | ------------------ |
| `main` / latest | :white_check_mark: |
| older alpha tags | :x:             |

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Report it privately through one of these channels:

1. **Preferred — GitHub private vulnerability reporting.** Go to the
   repository's **Security** tab → **Report a vulnerability**. This opens a
   private advisory visible only to the maintainers.
2. **Email.** If you can't use the form, email **nseniak@gmail.com** with
   `coyodex security` in the subject line.

Please include:

- what the issue is and the impact you think it has,
- the steps to reproduce it (a minimal repo or map is ideal),
- the version / commit you saw it on,
- any suggested fix, if you have one.

We'll acknowledge your report, work with you on a fix, and credit you in the
release notes unless you'd rather stay anonymous.

## Scope and threat model

coyodex runs **locally**, driven from your AI coding agent. It reads your repo,
writes a map under `.coyodex/`, and renders a **standalone HTML viewer**. A few
things worth keeping in mind when assessing risk:

- The generated `project-map.html` inlines its assets and is meant to be opened
  in a browser. Reports about the viewer mishandling repo content (for example,
  unescaped file paths or code rendered into the page) are in scope.
- The Python tooling under `tools/` parses the map and analysis files. Reports
  about parsing untrusted map/analysis input unsafely are in scope.
- coyodex sends your code and map context to whatever AI agent / model you drive
  it with. How that third-party agent handles your data is **out of scope** for
  this policy — review your agent's own privacy and security terms.

Thanks for helping keep coyodex and its users safe.

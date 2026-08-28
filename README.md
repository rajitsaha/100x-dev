<div align="center">

<img src="assets/100xprism-logo.svg" alt="100xPrism logo" width="120" />

# 100xPrism

### Stop vibe coding. Ship production-grade software.

[![Version](https://img.shields.io/github/v/release/rajitsaha/100xprism?style=flat-square&label=version&color=brightgreen)](https://github.com/rajitsaha/100xprism/releases/latest)
[![npm](https://img.shields.io/npm/v/100xprism?style=flat-square&color=red)](https://www.npmjs.com/package/100xprism)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

**One source of truth.** 68 modules generate native config for **Claude Code · Cursor · Codex · Pi**. Quality gates run on every commit.

### 📖 **[Full documentation →](https://rajitsaha.github.io/100xprism/)**

<img src="assets/100xprism-hero.svg" alt="100xPrism — one config, every AI coding tool" width="100%" />

</div>

---

## Install

```bash
npm install -g 100xprism && 100xprism install   # any platform
cd your-project && 100xprism init               # set up a project
100xprism update                                # stay current
```

macOS and Linux can also use `curl -fsSL https://raw.githubusercontent.com/rajitsaha/100xprism/main/get.sh | bash`.
Native Windows is partial — [use WSL](https://rajitsaha.github.io/100xprism/#support) for full module support.

## The pipeline

```
/understand → /context → /issue → /spec → /fix → /commit
                                                    ↓
              /techdebt ← /gate → /grill → /pr → /push → /release
```

Every `/commit` and `/push` runs a 5-point gate — tests, security, build, Docker, cloud. Nothing ships without passing.

## What you get

| | |
|---|---|
| **68 modules** | 28 slash commands + 40 auto-trigger skills |
| **4 tools** | Claude Code · Cursor · Codex · Pi — one config, native output for each |
| **5-point gate** | Enforced by a `PreToolUse` hook, not a reminder |
| **2 Claude Code plugins** | GitHub + security guidance by default; the rest are opt-in |
| **Value economics** | Offline dashboard — token cost joined to observable git delivery |
| **7 database engines** | Postgres, Cloud SQL, Snowflake, Databricks, Athena, Presto, Oracle via `/db` |
| **27 SaaS CLIs** | `/connect` installs + authenticates from `.env` |

## Documentation

**[rajitsaha.github.io/100xprism](https://rajitsaha.github.io/100xprism/)** is the single documentation hub — install, every command, the full [supported/unsupported matrix](https://rajitsaha.github.io/100xprism/#support), [value economics](https://rajitsaha.github.io/100xprism/#economics), context optimization, deprecations, and troubleshooting.

[Changelog](CHANGELOG.md) · [Issues](https://github.com/rajitsaha/100xprism/issues) · [Releases](https://github.com/rajitsaha/100xprism/releases/latest)

---

<div align="center">

Built by [Rajit Saha](https://www.linkedin.com/in/rajsaha/) · MIT licensed

If this saves you time, **[star the repo](https://github.com/rajitsaha/100xprism)**.

</div>

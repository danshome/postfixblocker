## Purpose & Scope
This file provides instructions and tips for agents working inside this project—covering workflow, Git usage, repository conventions, build/test requirements, architecture, and PR expectations.

**Scope rules**
- The scope of an `AGENTS.md` file is the entire directory tree rooted at the folder that contains it.
- For every file you touch, you must obey instructions in any `AGENTS.md` whose scope includes that file.
- Deeper (more-nested) `AGENTS.md` files take precedence on conflicts.
- Direct system/developer/user instructions in the prompt always take precedence over `AGENTS.md`.
- `AGENTS.md` files may appear anywhere (e.g., `/`, `~`, or within repos) and may include PR-message expectations.

If an `AGENTS.md` includes programmatic checks, you **must run them all** and make a best effort to ensure they pass **after** your changes—even if your change seems trivial (e.g., docs).

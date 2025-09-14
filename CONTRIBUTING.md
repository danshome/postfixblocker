<!-- Updated to best practices on 2025-09-14; preserves project-specific content. -->
# Contributing

<!-- BEGIN GENERATED: CONTRIBUTING:MAIN -->

Thank you for your interest in contributing to {{PROJECT_NAME}} at {{ORG_NAME}}.
We welcome code, docs, tests, and examples. This guide explains how to get
started and what we expect in pull requests.

## Ways to Contribute

- Code: features, bug fixes, refactors
- Documentation: README, guides, examples
- Tests: unit/integration/e2e, fixtures
- Tooling: CI, linters, dev ergonomics

## Getting Started

1. Fork the repository and create a topic branch from `main`.
2. Set up your environment and run the full test suite locally.
3. Make focused commits with clear messages.
4. Open a PR early for feedback.

Common commands:

```bash
{{LINT_CMD}}
{{TEST_CMD}}
```

Example for this repo:

```bash
docker compose up -d
pytest -q
```

## Code Style and Standards

- Python: PEP8 style; keep changes minimal and focused.
- Commits: Prefer Conventional Commits (e.g., `feat:`, `fix:`, `docs:`).

Examples:

```
feat: add DB2 retry loop in blocker
fix(api): deduplicate string literals for jsonify keys
docs: update README Quickstart and links
```

## Pull Request Checklist

- [ ] Tests added/updated for changes
- [ ] Docs updated (README/INSTALL/CHANGELOG as needed)
- [ ] Screenshots included (if UI changes)
- [ ] Breaking changes called out in PR description

## Issue Triage

We use labels such as `bug`, `enhancement`, `help wanted`, `good first issue`.
Please include a minimal reproduction for bugs (logs, versions, steps to
reproduce) and a clear problem statement for feature requests.

## Conduct and Security

- Be respectful and follow our [Code of Conduct](CODE_OF_CONDUCT.md).
- Report security issues privately via [Security Policy](SECURITY.md).

<!-- END GENERATED: CONTRIBUTING:MAIN -->


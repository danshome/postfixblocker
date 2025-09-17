# Release Guide

This document describes how to cut and publish a new release of postfix-blocker.
It covers versioning, tagging, building artifacts, creating a GitHub Release,
and publishing to PyPI. It assumes you have maintainer access to the repository.

## TL;DR

- Use SemVer tags `vX.Y.Z`.
- Generate the changelog from history: `make changelog` (or set `AUTO_CHANGELOG=1` with `make release` to auto-generate and commit it during the release).
- In GitHub Actions, the Release workflow first runs `make ci` (full lint/build/tests) and aborts if anything fails.
- Run `make release` — tags first, pushes the current branch and tag to `origin`, builds artifacts, and (if `gh` is installed) creates a GitHub Release. If no existing v* tags are present, it creates an initial tag `v0.0.0`.
- Publish to PyPI with `make publish-pypi`.

## Prerequisites

- Python 3.9+ and Make
- Git configured with push access to `main`
- GitHub CLI `gh` authenticated (optional, for auto‑creating a GitHub Release)
- PyPI credentials set via one of:
  - `TWINE_API_KEY` (recommended)
  - or `TWINE_USERNAME` and `TWINE_PASSWORD`
- Clean working tree (no uncommitted changes)

## Versioning Policy

- Semantic Versioning: `MAJOR.MINOR.PATCH`
- Git tag format: `vX.Y.Z` (leading `v`)
- Version is derived from tags via `setuptools_scm` (configured in `pyproject.toml`).
  Therefore, you must create and push a tag for a final release version to be embedded in the build artifacts.

## Pre‑release Checklist

1. Ensure CI is green locally and on the default branch:
   - `make ci`
2. Generate/refresh CHANGELOG.md from Git history:
   - `make changelog`
   - Review the changes and commit the file: `git add CHANGELOG.md && git commit -m "docs(changelog): update for upcoming release"`
3. Ensure docs are up to date (README/INSTALL/etc.).
4. Verify you’re on `main` and synced with origin.

## Cut the Release

Recommended explicit flow (ensures correct version baked into artifacts):

1) Choose the version and create an annotated tag

```bash
VERSION=X.Y.Z
TAG=v$VERSION

git switch main
git pull --ff-only

git tag -a "$TAG" -m "postfix-blocker $VERSION"
git push origin "$TAG"
```

2) Build distributables (sdist + wheel)

```bash
make dist
```

This uses PEP 517 build and validates metadata with `twine check`.
Artifacts appear under `./dist`.

3) Create a GitHub Release (attach artifacts)

- If you have GitHub CLI:

```bash
gh release create "$TAG" dist/* \
  -t "postfix-blocker $VERSION" \
  -n "See CHANGELOG.md for details."
```

- Otherwise, create a release manually in the GitHub UI and upload files from `dist/`.

4) Publish to PyPI

Ensure credentials are configured (prefer `TWINE_API_KEY`). Then:

```bash
make publish-pypi
```

This runs `twine upload dist/*`.

5) Verify

```bash
python -m pip install -U postfix-blocker==$VERSION
python -c "import postfix_blocker as p; print(p.__version__)"  # should print $VERSION
```

## Alternative: Makefile Shortcut

- `make version` — print the version setuptools-scm would compute right now
- `make changelog` — generate CHANGELOG.md from Git history (Conventional Commits aware)
- `make dist` — clean and build sdist+wheel and run `twine check`
- `make release` — create/verify a SemVer Git tag first (creates `v0.0.0` if no tags exist), optionally generate and commit the changelog when `AUTO_CHANGELOG=1`, push the current branch and tag to `origin`, build artifacts and (if `gh` is installed) create a GitHub Release and attach artifacts. You can override the version with `NEW_VERSION=X.Y.Z`.
- `make publish-pypi` — upload `dist/*` to PyPI via `twine`

## One-click Release in GitHub Actions

You can cut a release from the GitHub UI without a local environment:

1. Go to Actions → Release → Run workflow
2. Enter the version (e.g., `0.0.1`) and run
3. The workflow will:
   - create/annotate tag `vX.Y.Z`
   - auto-generate and commit CHANGELOG.md
   - push the branch and tag
   - build sdist+wheel and attach them to a GitHub Release

Requirements: the repo must allow the default `GITHUB_TOKEN` to push to the default branch and create releases (we set `permissions: contents: write`).

## TestPyPI (optional)

You can stage a release on TestPyPI before publishing to PyPI:

```bash
# Build as usual
make dist

# Upload to TestPyPI
python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# Install from TestPyPI (may need to specify dependencies from PyPI)
python -m pip install -U --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple postfix-blocker==$VERSION
```

## Rollback / Yanking

- If a tag was pushed mistakenly:

```bash
git push --delete origin vX.Y.Z
git tag -d vX.Y.Z
```

- PyPI: you cannot delete files immediately; consider yanking the release on PyPI or publishing a patched version (e.g., `X.Y.Z.post1`).
- GitHub Release: delete the release and re‑upload if needed.

## Troubleshooting

- Artifact version does not match tag: you probably built before tagging. Re‑tag (or tag correctly), run `make dist-clean`, then rebuild (`make dist`).
- `twine upload` fails: ensure `TWINE_API_KEY` is set (or username/password). You can test credentials with `twine upload --repository testpypi`.
- Wheels missing: ensure `build` is installed (Makefile installs it automatically during `make dist`).
- `.egg-info` directory appears after build: this is expected metadata written by setuptools during sdist/wheel builds. It is not an old "egg" distribution. Our Makefile now cleans it automatically after `make dist` and inside `make release`. You can also remove it manually with `rm -rf *.egg-info`.
- GitHub CLI errors: run `gh auth login` and ensure you have `GITHUB_TOKEN` set for CI environments.

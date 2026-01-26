# FeedSpine v0.1.0 Release Checklist

## Priority Legend
- **P0** = Must have for release (blocking)
- **P1** = Should have for release (important)
- **P2** = Nice to have (can follow up)
- **P3** = Future consideration

---

## P0: Critical (Must Complete Before Release)

### Repository Setup
- [x] Add MIT LICENSE file
- [x] Create CHANGELOG.md (Keep a Changelog format)
- [x] Create GitHub Actions CI workflow (test, lint, docs)
- [x] Create GitHub Actions publish workflow (PyPI)
- [x] Create enhanced README.md with badges, quick start, examples
- [ ] Rename README_NEW.md to README.md (replace existing)
- [ ] Push code to GitHub repository (currently empty)

### pyproject.toml Fixes
- [ ] Add `[project.urls]` section:
  ```toml
  [project.urls]
  Homepage = "https://github.com/ryansmccoy/feedspine"
  Documentation = "https://ryansmccoy.github.io/feedspine/"
  Repository = "https://github.com/ryansmccoy/feedspine"
  Changelog = "https://github.com/ryansmccoy/feedspine/blob/main/CHANGELOG.md"
  Issues = "https://github.com/ryansmccoy/feedspine/issues"
  ```

### Testing
- [ ] Verify all 448 tests pass locally
- [ ] Run tests on Python 3.11, 3.12, 3.13
- [ ] Verify doctests pass (`pytest --doctest-modules src/`)
- [ ] Check test coverage is >80%

### Build Verification
- [ ] Run `uv build` and verify wheel/sdist created
- [ ] Test install from wheel in clean virtualenv
- [ ] Verify `import feedspine` works
- [ ] Verify `feedspine --version` CLI works

---

## P1: Important (Should Complete Before Release)

### Documentation
- [ ] Ensure `mkdocs build --strict` passes (no warnings)
- [ ] Complete "Your First Feed" tutorial (currently placeholder)
- [ ] Complete "Implement a Custom Feed" how-to guide
- [ ] Add architecture diagram (Mermaid or image)
- [ ] Review all "Coming Soon" placeholders

### GitHub Repository
- [ ] Write repository description: "Storage-agnostic feed capture framework with deduplication and medallion architecture"
- [ ] Add topics: `python`, `data-pipeline`, `etl`, `feeds`, `rss`, `deduplication`, `medallion-architecture`
- [ ] Create initial GitHub release (v0.1.0) with release notes
- [ ] Enable GitHub Pages for documentation

### Documentation Hosting
- [ ] Configure GitHub Pages (Settings → Pages → Deploy from branch)
- [ ] Add `.github/workflows/docs.yml` for auto-deploy on push to main
- [ ] Verify docs deploy to https://ryansmccoy.github.io/feedspine/

### PyPI Setup
- [ ] Create PyPI account if not exists
- [ ] Create TestPyPI account
- [ ] Configure Trusted Publisher (PyPI project → Settings → Publishing)
- [ ] Test publish to TestPyPI first
- [ ] Verify install from TestPyPI works

---

## P2: Nice to Have (Can Follow Up After Release)

### Repository Polish
- [ ] Add SECURITY.md (security policy)
- [ ] Add CODE_OF_CONDUCT.md
- [ ] Create issue templates (bug report, feature request)
- [ ] Create pull request template
- [ ] Add CODEOWNERS file

### Documentation Enhancements
- [ ] Generate API reference with mkdocstrings
- [ ] Add more code examples in docstrings
- [ ] Create "Migrating from feedparser" guide
- [ ] Add FAQ page
- [ ] Record demo video/GIF for README

### Code Quality
- [ ] Run `interrogate` to check docstring coverage (target: 80%)
- [ ] Add pre-commit hooks configuration
- [ ] Add dependabot.yml for dependency updates

---

## P3: Future (Post-Release Backlog)

### Additional Backends
- [ ] PostgreSQL storage backend
- [ ] Redis cache backend
- [ ] SQLite storage backend
- [ ] S3 blob storage backend

### Features
- [ ] CLI commands for common operations
- [ ] Webhook adapter
- [ ] Prometheus metrics export
- [ ] OpenTelemetry tracing

### Ecosystem
- [ ] Create py-sec-edgar v4 with FeedSpine integration
- [ ] Blog post announcement
- [ ] Submit to Python Weekly newsletter
- [ ] Reddit r/Python announcement

---

## Release Day Checklist

### Before Publishing
- [ ] Final `uv sync && uv run pytest` passes
- [ ] Final `uv run ruff check src tests` passes
- [ ] Final `uv run mypy src` passes
- [ ] Version in `pyproject.toml` is `0.1.0`
- [ ] CHANGELOG.md date is set to release date
- [ ] All P0 items complete

### Publishing
- [ ] Create git tag: `git tag v0.1.0`
- [ ] Push tag: `git push origin v0.1.0`
- [ ] Create GitHub Release from tag
- [ ] Verify GitHub Actions publishes to PyPI
- [ ] Verify `pip install feedspine` works

### After Publishing
- [ ] Verify PyPI page looks correct
- [ ] Verify documentation is live
- [ ] Post announcement (Twitter/X, LinkedIn, Reddit)
- [ ] Monitor GitHub issues for first-user feedback

---

## Version Strategy

For 0.x releases:
- **0.1.0** - Initial public release
- **0.1.x** - Bug fixes only
- **0.2.0** - New features, possible breaking changes (documented in CHANGELOG)
- **1.0.0** - Stable API, breaking changes require major version bump

The 0.x series signals "API may change" to users. Use this time to gather feedback
and refine the API before committing to stability in 1.0.0.

---

## Success Metrics

### Week 1
- [ ] Package installable via pip
- [ ] Documentation accessible
- [ ] Zero critical bugs reported

### Month 1
- [ ] 10+ GitHub stars
- [ ] 100+ PyPI downloads
- [ ] First external contribution

### Month 3
- [ ] 50+ GitHub stars
- [ ] 1,000+ PyPI downloads
- [ ] Featured in a newsletter or blog

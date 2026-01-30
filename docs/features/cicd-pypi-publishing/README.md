# CI/CD & PyPI Publishing

> **Getting projects into GitHub Actions and PyPI**  
> Automated testing, building, and publishing

---

## Publication Strategy

| Project | Visibility | PyPI | GitHub | Notes |
|---------|-----------|------|--------|-------|
| **py-sec-edgar** | Public | ✅ Published | ✅ Public | Already live |
| **entityspine** | Public | ✅ Published | ✅ Public | Already live |
| **feedspine** | Public → PyPI | ⏳ Planned 1.0.0 | ✅ Public | Ready for release |
| **spine-core** | Public | ❓ TBD | ✅ Public | May stay git-only |
| **capture-spine** | Private | ❌ Never | 🔒 Private | Keep private |
| **trading-desktop** | Private | ❌ Never | 🔒 Private | Keep private |

---

## Project Status

### py-sec-edgar ✅

**Current State:** Published to PyPI, GitHub Actions in place

```bash
pip install py-sec-edgar
```

**CI/CD:**
- ✅ GitHub Actions: test on push/PR
- ✅ PyPI publish on tag
- ✅ ReadTheDocs integration

### entityspine ✅

**Current State:** Published to PyPI

```bash
pip install entityspine
```

**CI/CD:**
- ✅ GitHub Actions: test on push/PR
- ✅ PyPI publish on tag

### feedspine ⏳

**Current State:** Ready for 1.0.0 release

```bash
# Currently
pip install git+https://github.com/user/feedspine.git

# Goal
pip install feedspine
```

**CI/CD Needed:**
- ⏳ GitHub Actions workflow
- ⏳ PyPI publishing
- ⏳ Version 1.0.0 tag

### spine-core ❓

**Current State:** On GitHub, not on PyPI

**Options:**
1. **Git dependency** (current) - consumers add to requirements
2. **PyPI publish** - full package
3. **Monorepo sub-package** - include in feedspine

**Recommendation:** Keep as git dependency for now, revisit after feedspine 1.0.0

### capture-spine 🔒

**Status:** KEEP PRIVATE

- Private GitHub repo
- No PyPI publication
- Internal use only

### trading-desktop 🔒

**Status:** KEEP PRIVATE

- Private GitHub repo
- No PyPI publication
- Internal use only

---

## feedspine CI/CD Setup

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      
      - name: Run tests
        run: |
          pytest --cov=feedspine --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install linters
        run: |
          pip install ruff mypy
      
      - name: Run ruff
        run: ruff check src/
      
      - name: Run mypy
        run: mypy src/feedspine
```

### PyPI Publishing Workflow

```yaml
# .github/workflows/publish.yml

name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # For trusted publishing
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install build tools
        run: |
          pip install build twine
      
      - name: Build package
        run: python -m build
      
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # Uses trusted publishing - no API token needed
```

### pyproject.toml for Publishing

```toml
# feedspine/pyproject.toml

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "feedspine"
version = "1.0.0"
description = "Feed management and observation comparison engine"
readme = "README.md"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "you@example.com"}
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
requires-python = ">=3.10"
dependencies = [
    "entityspine>=0.1.0",
    "pydantic>=2.0",
    # Add other deps
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
    "pytest-asyncio",
    "ruff",
    "mypy",
]

[project.urls]
Homepage = "https://github.com/user/feedspine"
Documentation = "https://feedspine.readthedocs.io"
Repository = "https://github.com/user/feedspine"

[tool.setuptools.packages.find]
where = ["src"]
```

---

## PyPI Trusted Publishing Setup

Modern PyPI uses "Trusted Publishers" - no API tokens needed:

1. **Go to PyPI** → Account Settings → Publishing
2. **Add New Pending Publisher:**
   - Project: `feedspine`
   - Owner: `your-github-username`
   - Repository: `feedspine`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. **Create GitHub Environment:**
   - Settings → Environments → New: `pypi`
   - Add protection rules (optional)

---

## Version Strategy

### Semantic Versioning

```
MAJOR.MINOR.PATCH

1.0.0 - Initial stable release
1.1.0 - New features, backward compatible
1.1.1 - Bug fixes
2.0.0 - Breaking changes
```

### Release Checklist

```markdown
## feedspine 1.0.0 Release Checklist

- [ ] All tests passing
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped in pyproject.toml
- [ ] Tag created: `git tag v1.0.0`
- [ ] GitHub Release created
- [ ] PyPI publish triggered
- [ ] Install tested: `pip install feedspine==1.0.0`
```

---

## Dependency Graph

```
             ┌─────────────────────────────────────┐
             │            PyPI (Public)            │
             └─────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌───────────┐    ┌───────────┐    ┌───────────┐
   │py-sec-edgar│   │ entityspine│   │ feedspine │
   │   (PyPI)  │    │   (PyPI)  │    │  (PyPI)   │
   └───────────┘    └───────────┘    └───────────┘
                           │                │
                           └────────┬───────┘
                                    │
                                    ▼
                           ┌───────────────┐
                           │  spine-core   │
                           │  (git dep)    │
                           └───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
           ┌───────────────┐               ┌───────────────┐
           │ capture-spine │               │trading-desktop│
           │  (PRIVATE)    │               │  (PRIVATE)    │
           └───────────────┘               └───────────────┘
```

---

## Implementation Tasks

### Phase 1: feedspine 1.0.0

| Task | Status |
|------|--------|
| Finalize pyproject.toml | ⏳ |
| Create .github/workflows/ci.yml | ⏳ |
| Create .github/workflows/publish.yml | ⏳ |
| Set up PyPI trusted publisher | ⏳ |
| Create GitHub environment | ⏳ |
| Write CHANGELOG.md | ⏳ |
| Tag v1.0.0 | ⏳ |
| Verify PyPI installation | ⏳ |

### Phase 2: spine-core (Optional)

| Task | Status |
|------|--------|
| Decide: PyPI vs git dependency | ⏳ |
| If PyPI: set up publishing | ⏳ |
| Update consumers to use new source | ⏳ |

---

## Related Docs

- [ECOSYSTEM.md](../../../../ECOSYSTEM.md) - Project integration overview
- [py-sec-edgar PyPI](https://pypi.org/project/py-sec-edgar/)
- [entityspine PyPI](https://pypi.org/project/entityspine/)

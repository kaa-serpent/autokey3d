# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Reference Docs

Read the relevant doc before modifying related code.

- [docs/architecture.md](docs/architecture.md) — Two-layer design, data concepts, external tool dependencies
- [docs/profile.md](docs/profile.md) — Profile parameters, files, tolerance, handle connectors
- [docs/system.md](docs/system.md) — System definition parameters, special cases, custom modules
- [docs/generation.md](docs/generation.md) — `generate_key()` pipeline, CLI args, SVG→DXF, settings.scad composition
- [docs/data.md](docs/data.md) — ProfileIndex, profiles.json structure, testing
- [docs/web.md](docs/web.md) — Flask web app pages, API endpoints, job store, template structure
- [docs/docker.md](docs/docker.md) — Docker setup, Xvfb, persistence

## Commands

### With Docker (no local installs needed)

```bash
# Build and start (http://localhost:5000)
docker compose up --build

# Subsequent starts (no rebuild needed unless Dockerfile/requirements changed)
docker compose up
```

### Without Docker (local venv)

All commands must be run in the venv.

```bash
# Launch the web app (http://localhost:5000)
python web_app.py

# CLI key generation (backward-compatible)
python AutoKey.py --bumpkey --profile profiles/AB-AB95.svg --definition definitions/AB-E20.scad
python AutoKey.py --blank   --profile profiles/AB-AB1.svg  --definition definitions/AB-C83.scad
python AutoKey.py --key 1,2,3,4,5 --profile profiles/AB-AB1.svg --definition definitions/AB-C83.scad

# Run all tests
python -m pytest tests/

# Run a single test class or test
python -m pytest tests/test_profile_index.py::TestProfileIndex

# Install dependencies
pip install -r requirements.txt
```

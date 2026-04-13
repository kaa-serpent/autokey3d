# Docker Reference

## What's in the image

| Component | Version source |
|-----------|---------------|
| Python 3 + Flask | `requirements.txt` installed into `/venv` |
| OpenSCAD | Debian `bookworm` apt package |
| Inkscape | Debian `bookworm` apt package |
| Xvfb | Debian `bookworm` apt package — provides the virtual display that OpenSCAD and Inkscape require on Linux |

## Running (recommended — with docker-compose)

```bash
docker compose up --build
```

Open [http://localhost:5000](http://localhost:5000).

The project directory is bind-mounted as `/app` inside the container, so:
- profiles, definitions, and `profiles.json` are read from — and written back to — your host directory.
- New profiles/systems added through the web UI persist across container restarts.
- Changes to Python source files take effect on the next `docker compose up`.

## Running (standalone — no persistence)

```bash
docker build -t autokey3d .
docker run -p 5000:5000 autokey3d
```

Without a volume mount, new profiles/systems are saved inside the container and lost when the container stops.

## How the virtual display works

`docker/entrypoint.sh` starts `Xvfb :99` as a background process and sets `DISPLAY=:99` before Flask starts. OpenSCAD and Inkscape connect to this display when invoked by key generation requests.

## Rebuilding after dependency changes

If you change `requirements.txt` or the `Dockerfile`, rebuild with:

```bash
docker compose up --build
```

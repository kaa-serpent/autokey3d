FROM debian:bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99

# System dependencies:
#   openscad  — headless STL export
#   inkscape  — flattens <text> in branding SVG to paths before DXF conversion
#   xvfb      — virtual framebuffer (OpenSCAD and Inkscape need a display on Linux)
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        openscad \
        inkscape \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies into an isolated venv at /venv so a bind-mount
# of the project directory (see docker-compose.yml) does not shadow them.
COPY requirements.txt .
RUN python3 -m venv /venv \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker/entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["docker/entrypoint.sh"]

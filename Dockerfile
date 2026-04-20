FROM python:3.12-slim AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl docker.io libpq-dev socat \
    && rm -rf /var/lib/apt/lists/*

RUN arch="$(dpkg --print-architecture)" \
    && case "$arch" in \
        amd64) docker_arch="x86_64" ;; \
        arm64) docker_arch="aarch64" ;; \
        *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "https://download.docker.com/linux/static/stable/${docker_arch}/docker-26.1.4.tgz" -o /tmp/docker.tgz \
    && tar -xzf /tmp/docker.tgz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && chmod +x /usr/local/bin/docker \
    && rm -rf /tmp/docker /tmp/docker.tgz

COPY pyproject.toml ./
RUN pip install -e ".[observability,platform,safety,evals,dev]"

COPY . .
RUN pip install -e ".[observability,platform,safety,evals,dev]"
RUN mv /usr/local/bin/docker /usr/local/bin/docker-real
RUN install -D -m 755 scripts/docker-relay-wrapper.sh /usr/local/bin/docker

# ------------------------------------------------------------------
# Factory API target
# ------------------------------------------------------------------
FROM base AS factory
EXPOSE 8000
CMD ["uvicorn", "factory.main:app", "--host", "0.0.0.0", "--port", "8000"]

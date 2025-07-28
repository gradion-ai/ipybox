FROM ubuntu:22.04

# Add arguments for UID and GID
ARG UID=1000
ARG GID=1000
ENV HOME=/home/appuser

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    iptables \
    ipset \
    dnsutils \
    iproute2 \
    aggregate \
    netcat-openbsd \
    libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22.x
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.8.3 /uv /uvx /bin/

RUN groupadd -g ${GID} appuser && \
    useradd -u ${UID} -g appuser -m -s /bin/bash appuser

WORKDIR ${HOME}

USER appuser

# Copy dependency files first for better Docker layer caching
COPY --chown=appuser:appuser pyproject.toml .python-version ${HOME}/

# Install Python dependencies using uv (skip project install to avoid git dependency)
RUN uv sync --no-dev --no-install-project

COPY --chown=appuser:appuser server.sh ${HOME}/
RUN chmod +x ${HOME}/server.sh

COPY --chown=appuser:appuser ipybox/resource /app/ipybox/resource/
COPY --chown=appuser:appuser ipybox/mcp /app/ipybox/mcp/
COPY --chown=appuser:appuser ipybox/modinfo.py /app/ipybox/

USER root

COPY init-firewall.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-firewall.sh

USER appuser

WORKDIR /app

# Use uv to run the entrypoint with activated virtual environment
CMD ["/bin/bash", "-c", "source ${HOME}/.venv/bin/activate && ${HOME}/server.sh"]

FROM ubuntu:22.04

# Build arguments for user ID matching
ARG UID=1000
ARG GID=1000

# Create user with matching UID/GID
RUN groupadd -g ${GID} ipybox && \
    useradd -m -u ${UID} -g ipybox ipybox

ENV HOME=/home/ipybox

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22.x
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.15 /uv /uvx /bin/

WORKDIR ${HOME}

# Bypass dynamic versioning since .git is not available
ENV UV_DYNAMIC_VERSIONING_BYPASS=0.0.0+docker

# Create workspace directory with correct ownership
RUN mkdir -p /app/workspace && chown ipybox:ipybox /app/workspace

# Copy entrypoint script (requires root)
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Copy dependency files first for better Docker layer caching
COPY --chown=ipybox:ipybox pyproject.toml uv.lock .python-version ${HOME}/

# Switch to non-root user before installing dependencies
USER ipybox

# Install dependencies only (not the project itself)
RUN uv sync --no-install-project --no-dev

# Copy source code and README (required for package metadata)
COPY --chown=ipybox:ipybox ipybox ${HOME}/ipybox/
COPY --chown=ipybox:ipybox README.md ${HOME}/

# Install the project
RUN uv sync --no-dev

WORKDIR /app/workspace

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

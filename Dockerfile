FROM ubuntu:22.04

ENV HOME=/root

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

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml uv.lock .python-version ${HOME}/

# Install dependencies only (not the project itself)
RUN uv sync --no-install-project --no-dev

# Copy source code and README (required for package metadata)
COPY ipybox ${HOME}/ipybox/
COPY README.md ${HOME}/

# Install the project
RUN uv sync --no-dev

# Create workspace directory
RUN mkdir -p /app/workspace

WORKDIR /app/workspace

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

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

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml .python-version ${HOME}/

# Install Python dependencies using uv (skip project install to avoid git dependency)
RUN uv sync --no-dev --no-install-project

# Copy source code
COPY ipybox ${HOME}/ipybox/

# Install the project
RUN uv sync --no-dev

# Create workspace directory
RUN mkdir -p /app/workspace

WORKDIR /app/workspace

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

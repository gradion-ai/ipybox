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

# Create virtual environment and install dependencies only (not the project itself)
RUN uv venv && uv pip install -r pyproject.toml

# Copy source code
COPY ipybox ${HOME}/ipybox/

# Install the project in editable mode (no git needed for this)
RUN uv pip install --no-deps -e .

# Create workspace directory
RUN mkdir -p /app/workspace

WORKDIR /app/workspace

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

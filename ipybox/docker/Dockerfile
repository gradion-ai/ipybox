FROM ubuntu:22.04

# Add arguments for UID and GID
ARG UID=1000
ARG GID=1000
ENV HOME=/home/appuser

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    ca-certificates \
    curl \
    wget \
    iptables \
    ipset \
    dnsutils \
    iproute2 \
    aggregate \
    netcat-openbsd \
    libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs

RUN groupadd -g ${GID} appuser && \
    useradd -u ${UID} -g appuser -m -s /bin/bash appuser

WORKDIR ${HOME}

USER appuser

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh \
    && bash miniconda.sh -b -p ${HOME}/conda \
    && rm miniconda.sh

RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=${HOME}/poetry python3 -

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="${HOME}/conda/bin:${PATH}"
ENV PATH="${HOME}/poetry/bin:${PATH}"
ENV PATH="${HOME}/.local/bin:${PATH}"

COPY --chown=appuser:appuser environment.yml ${HOME}/
RUN conda env create -f ${HOME}/environment.yml -n ipybox && conda init bash

COPY --chown=appuser:appuser pyproject.toml ${HOME}/
RUN poetry config virtualenvs.create false
RUN conda run -n ipybox poetry install --only main

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

CMD ["/bin/bash", "-c", "source ${HOME}/conda/etc/profile.d/conda.sh && conda activate ipybox && ${HOME}/server.sh"]

#!/bin/bash
set -e

exec ${HOME}/.venv/bin/ipybox \
    --workspace /app/workspace \
    --tool-server-host localhost \
    --tool-server-port 8900 \
    --kernel-gateway-host localhost \
    --kernel-gateway-port 8888 \
    --log-level INFO

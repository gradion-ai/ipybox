#!/bin/bash
set -e

docker build \
    --build-arg UID=$(id -u) \
    --build-arg GID=$(id -g) \
    -t ipybox \
    "$@" \
    .

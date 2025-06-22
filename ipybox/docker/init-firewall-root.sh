#!/bin/bash
# Firewall initialization script for root containers
# This script is used when the container runs as root user

echo "ERROR: Firewall setup is disabled because the container runs as root." >&2
echo "Build an ipybox image without -r or --root to enable firewall support." >&2
exit 1

#!/bin/bash

jupyter kernelgateway \
  --KernelGatewayApp.ip=0.0.0.0 \
  --KernelGatewayApp.port=8888 &

python -m ipybox.resource.server \
  --root-dir=/app \
  --host=0.0.0.0 \
  --port=8900

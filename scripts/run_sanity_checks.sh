#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT_DIR"

status() {
  printf '\n== %s ==\n' "$1"
}

status "Python bytecode compilation"
python -m compileall ecommerce-order-system >/dev/null

docker_compose_available=false
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker_compose_available=true
fi

if $docker_compose_available; then
  status "Validating REST docker-compose.yml"
  (cd REST-Server-Client && docker compose config >/dev/null)

  status "Validating gRPC docker-compose.yml"
  (cd ecommerce-order-system && docker compose config >/dev/null)
else
  echo "Docker Compose not available. Skipping compose validation."
fi

status "Summary"
echo "Sanity checks completed. Use docker compose up ... to run full integration tests."

#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="$ROOT_DIR/artifacts"
LOG_DIR="$ARTIFACT_DIR/logs"
SCREEN_DIR="$ARTIFACT_DIR/screens"
SUMMARY_FILE="$ARTIFACT_DIR/harness-summary.csv"

mkdir -p "$LOG_DIR" "$SCREEN_DIR"
: > "$SUMMARY_FILE"
printf 'name,status,log,screen\n' > "$SUMMARY_FILE"

REST_BASE_URL="${REST_BASE_URL:-http://localhost:8080}"
REST_CLIENT_DIR="$ROOT_DIR/REST-Server-Client/src/clients"
REST_SMOKE_SCRIPT="$REST_CLIENT_DIR/smoke.sh"
PYTEST_TARGET="$ROOT_DIR/tests/test_microservices.py"
PYTHONPATH_VALUE="$ROOT_DIR/ecommerce-order-system/user_service:$ROOT_DIR/ecommerce-order-system/product_service:$ROOT_DIR/ecommerce-order-system/order_service:$ROOT_DIR/ecommerce-order-system/payment_service:$ROOT_DIR/ecommerce-order-system/shipping_service"
if [[ -n "${PYTHONPATH:-}" ]]; then
  PYTHONPATH_VALUE="$PYTHONPATH_VALUE:$PYTHONPATH"
fi

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

overall_status=0

run_step() {
  local name="$1"
  shift
  local log_file="$LOG_DIR/${name}.log"
  local screen_file="$SCREEN_DIR/${name}.txt"
  local exit_code=0
  {
    printf '[%s] START %s\n' "$(timestamp)" "$name"
    "$@"
  } > >(tee "$screen_file") 2>&1 || exit_code=$?
  cp "$screen_file" "$log_file"
  printf '%s,%s,%s,%s\n' "$name" "$exit_code" "$log_file" "$screen_file" >> "$SUMMARY_FILE"
  if (( exit_code != 0 )) && (( overall_status == 0 )); then
    overall_status=$exit_code
  fi
}

record_skip() {
  local name="$1"
  local message="$2"
  local log_file="$LOG_DIR/${name}.log"
  local screen_file="$SCREEN_DIR/${name}.txt"
  printf '[%s] SKIP %s\n%s\n' "$(timestamp)" "$name" "$message" | tee "$screen_file"
  cp "$screen_file" "$log_file"
  printf '%s,%s,%s,%s\n' "$name" "SKIPPED" "$log_file" "$screen_file" >> "$SUMMARY_FILE"
}

printf '\n[HARNESS] Output directory: %s\n' "$ARTIFACT_DIR"

if [[ -x "$REST_SMOKE_SCRIPT" ]] && command -v curl >/dev/null 2>&1; then
  if curl -fsS --max-time 5 "${REST_BASE_URL%/}/api/products" >/dev/null 2>&1; then
    run_step rest_smoke bash -c "cd '$REST_CLIENT_DIR' && BASE_URL='$REST_BASE_URL' ./smoke.sh"
  else
    record_skip rest_smoke "REST base URL $REST_BASE_URL is unreachable. Ensure the Docker stack is running before rerunning the harness."
  fi
else
  record_skip rest_smoke "Smoke script not executable or curl missing."
fi

if [[ -f "$PYTEST_TARGET" ]]; then
  run_step grpc_pytest bash -c "cd '$ROOT_DIR' && PYTHONPATH='$PYTHONPATH_VALUE' pytest '$PYTEST_TARGET' -vv"
else
  record_skip grpc_pytest "Pytest target $PYTEST_TARGET not found."
fi

printf '\n[HARNESS] Summary written to %s\n' "$SUMMARY_FILE"
exit $overall_status

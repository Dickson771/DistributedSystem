#!/usr/bin/env bash
set -euo pipefail

# Change if you’re behind nginx: BASE_URL=http://localhost:8080 ./smoke.sh
BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "== Smoke: list products =="
curl -fsS "${BASE_URL%/}/api/products" || { echo "List products failed"; exit 1; }
echo

echo "== Smoke: product detail id=1 =="
curl -fsS "${BASE_URL%/}/api/products/1" || true
echo

echo "== Smoke: register user =="
USER_JSON='{"name":"Alice","email":"alice@example.com","password":"pass"}'
USER_RESP=$(curl -fsS -H "Content-Type: application/json" -X POST \
  -d "$USER_JSON" "${BASE_URL%/}/api/users") || { echo "Register failed"; exit 1; }
echo "$USER_RESP"
USER_ID=$(echo "$USER_RESP" | sed -n 's/.*"id":[ ]*\([0-9]\+\).*/\1/p')
: "${USER_ID:=1}"
echo "USER_ID=$USER_ID"

echo "== Smoke: place order =="
ORDER_JSON='{"userId":'"$USER_ID"',"productIds":[1,2],"address":"123 Demo St","payment":"card","shipping":"std"}'
ORDER_RESP=$(curl -fsS -H "Content-Type: application/json" -X POST \
  -d "$ORDER_JSON" "${BASE_URL%/}/api/orders") || { echo "Order failed"; exit 1; }
echo "$ORDER_RESP"
ORDER_ID=$(echo "$ORDER_RESP" | sed -n 's/.*"orderId":[ ]*\([0-9]\+\).*/\1/p')
: "${ORDER_ID:=1}"
echo "ORDER_ID=$ORDER_ID"

echo "== Smoke: list my orders (filter) =="
curl -fsS "${BASE_URL%/}/api/orders?userId=${USER_ID}" || { echo "List my orders failed"; exit 1; }
echo

echo "== Smoke: get order by id =="
curl -fsS "${BASE_URL%/}/api/orders/${ORDER_ID}" || { echo "Get order failed"; exit 1; }
echo

echo "== Smoke: update order status =="
curl -fsS -H "Content-Type: application/json" -X PUT \
  -d '{"status":"processed"}' \
  "${BASE_URL%/}/api/orders/${ORDER_ID}" || { echo "Update failed"; exit 1; }
echo

echo "== Smoke: cancel order =="
curl -fsS -X DELETE "${BASE_URL%/}/api/orders/${ORDER_ID}" || { echo "Delete failed"; exit 1; }
echo

echo "All smoke tests passed ✅"

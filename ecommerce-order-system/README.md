# gRPC Microservice E-commerce System

This directory contains the Python/gRPC implementation of the distributed ordering workflow. Five independent services (user, product, order, payment, shipping) communicate over gRPC and are orchestrated with Docker Compose.

---

## Prerequisites
- Docker Desktop/Engine with Docker Compose v2
- Python 3.11+
- `pip install -r client/requirements.txt` for local CLI or testing

---

## Quickstart (Docker Compose)
```bash
cd ecommerce-order-system
# Re-generate protobuf code when .proto files change
python generate_protos.py

# Build and launch all containers
docker compose up -d --build

# Connect to the interactive client and walk through the flows
CLIENT_CONTAINER=$(docker compose ps --services | grep client)
docker exec -it "$CLIENT_CONTAINER" bash -lc "python client.py"
```

Each microservice exposes its own health logs. Tail everything via `docker compose logs -f` or inspect individual services with `docker compose logs user_service`.

---

## Local Service Execution (without Docker)
For rapid iteration, you can run services directly with Python. Each service listens on localhost ports 50051–50055.

```bash
# Example: start the user service locally
cd ecommerce-order-system/user_service
python user_server.py
```

Repeat for the remaining services in separate terminals. The CLI in `client/client.py` can then be pointed to localhost by editing the hostnames inside the script.

---

## Automated Testing
The repository-wide harness delegates to `pytest tests/test_microservices.py`, which exercises the core gRPC workflow completely in-process (no network sockets required). Run it from the repository root or directly from this folder:

```bash
cd ..  # repository root
PYTHONPATH="ecommerce-order-system/user_service:...:ecommerce-order-system/shipping_service" \
    pytest tests/test_microservices.py -vv
```

Logs and terminal screenshots are captured under `artifacts/` when you launch `./scripts/run_test_harness.sh`.

---

## Troubleshooting & Assumptions
- The services use in-memory stores for simplicity; restarting containers resets state.
- The checked-in protobuf stubs were generated with `grpcio-tools >= 1.74`. If your environment ships an older runtime, use the compatibility shim bundled in `tests/test_microservices.py` or re-run `python generate_protos.py` with a matching compiler.
- Container names follow the pattern `ecommerce-order-system-<service>-1`. Use `docker compose ps` to confirm the actual name before running `docker exec` commands.

# Distributed E-Commerce System
**CSE 5306 – Distributed Systems (Fall 2025)**  
**Team Members:**
* Nebi Malik – RESTful Server–Client Architecture (C++ / HTTP)
* Saheed Oladele – Microservice Architecture (Python / gRPC)

Repository link: https://github.com/nebimal/DistributedSystem

---

## Overview
This project implements a **distributed e-commerce system** using **two complementary system architectures** to compare performance, scalability, and design trade-offs:

1. **RESTful Server–Client Architecture (C++ Crow Framework)**
   * Focuses on simplicity and HTTP-based interaction.
   * Implements REST APIs, Nginx load balancing, PostgreSQL for persistence, and Redis caching.
   * Includes a Bash-based smoke test client for validation.

2. **Microservice gRPC Architecture (Python)**
   * Focuses on modularity and efficient inter-service communication via gRPC.
   * Each service (User, Product, Order, Payment, Shipping) runs in an isolated container and exposes strongly-typed contracts.
   * Includes a scripted pytest flow to exercise an end-to-end order lifecycle without needing live gRPC servers.

Both architectures simulate core e-commerce functionality like browsing products, registering users, placing orders, and processing payments and shipping, but differ in **communication model**, **deployment structure**, and **scalability characteristics**.

---

## Build & Run Quickstart
The repository is split into two self-contained stacks. Work from the repository root and follow the corresponding instructions.

### 1. REST Server–Client (`REST-Server-Client`)
```bash
cd REST-Server-Client
docker compose down
docker compose up -d --build
docker compose stop api2  # keep a single in-memory API instance for now
# Wait for nginx to become available
for i in $(seq 1 30); do curl -sf http://localhost:8080 >/dev/null && break; sleep 1; done
# Run the bundled smoke tests
BASE_URL=http://localhost:8080 bash ./src/clients/smoke.sh
```

### 2. gRPC Microservices (`ecommerce-order-system`)
```bash
cd ecommerce-order-system
python3 -m venv .venv && source .venv/bin/activate
pip install -r client/requirements.txt
python generate_protos.py  # regenerates *_pb2.py files when proto files change
docker compose up -d --build
docker exec -it ecommerce-order-system-client-1 bash -lc "python client.py"
```

---

## Automated Test Harness
The repository now includes a scripted harness that coordinates both architectures and captures repeatable evidence:

```bash
bash ./scripts/run_test_harness.sh
```

What it does:
1. Creates `artifacts/logs/` and `artifacts/screens/` for raw logs and “terminal screenshots”.
2. Attempts to run the REST smoke test suite if the nginx endpoint is reachable (otherwise it records a skipped run).
3. Executes `pytest tests/test_microservices.py -vv`, which simulates user registration, catalog browsing, order creation, payment, and shipping flows directly against the Python service classes.
4. Summarizes results in `artifacts/harness-summary.csv` for quick reporting.

You can pass `REST_BASE_URL` to point the harness at a non-default endpoint (default: `http://localhost:8080`).

---

## Assumptions
* Docker Desktop/Engine and Docker Compose v2 are installed locally.
* `curl` is available for the REST smoke scripts.
* Python 3.11+ with `pytest`, `grpcio`, and `grpcio-tools` is available for the harness; a compatibility shim is bundled so tests can run even when the system Python ships an older protobuf/grpc runtime.
* Services are intended for instructional use and rely on in-memory state (no production-grade persistence or authentication flows).

---

## References
* [Crow C++ Microframework](https://github.com/CrowCpp/Crow)
* [gRPC Python Documentation](https://grpc.io/docs/languages/python/)
* [Docker Compose](https://docs.docker.com/compose/)
* [Project Repository](https://github.com/nebimal/DistributedSystem)

---

## How to Explore Further
1. Navigate to the corresponding project folder:
   * `cd REST-Server-Client`
   * `cd ecommerce-order-system`
2. Open the respective `README.md` file inside that folder for deeper build/run details and architecture diagrams.

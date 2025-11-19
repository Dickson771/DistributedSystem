# Distributed E-Commerce System  
**CSE 5306 – Distributed Systems (Fall 2025)**  
**Team Members:**  
- Nebi Malik – RESTful Server–Client Architecture (C++ / HTTP)  
- Saheed Oladele – Microservice Architecture (Python / gRPC)

---

## Overview
This project implements a **distributed e-commerce system** using **two different system architectures** to compare performance, scalability, and design trade-offs:

1. **RESTful Server–Client Architecture (C++ Crow Framework)**  
   - Focuses on simplicity and HTTP-based interaction.  
   - Implements REST APIs, Nginx load balancing, PostgreSQL for data persistence, and Redis caching.

2. **Microservice gRPC Architecture (Python)**  
   - Focuses on modularity and efficient inter-service communication via gRPC.  
   - Each service (User, Product, Order, Payment, Shipping) runs in an isolated container.

Both architectures simulate core e-commerce functionality like browsing products, registering users, placing orders, and processing payments and shipping, but differ in **communication model**, **deployment structure**, and **scalability characteristics**.

## How to Run
To execute either implementation:

1. Navigate to the corresponding project folder:  
   - `cd REST-Server-Client`  
   - `cd ecommerce-order-system`  

2. Open the respective `README.md` file inside that folder.
   Each README provides detailed steps to **build, run, and test** the system.

---

## Assignment 3 Workflow Helpers

For the consensus assignment, we often keep the deliverables for each question on its own branch
while iterating. Use the helper scripts below to merge them into a single submission branch and to
run lightweight sanity checks before packaging everything up.

### Merge multiple branches into one

```
# Merge branches q1-2pc, q2-decision, q3-raft, q4-log, q5-tests into assignment3-final
BASE_BRANCH=work \
  ./scripts/merge_branches.sh assignment3-final \
  q1-2pc q2-decision q3-raft q4-log q5-tests
```

The script enforces a clean working tree, creates (or reuses) the target branch from `BASE_BRANCH`,
and performs `--no-ff` merges so each task’s history stays visible. Resolve any conflicts as they
appear, rerun the script for the remaining branches, and you’ll end up with a consolidated branch
ready for testing and submission.

### Run repo-wide sanity checks

```
./scripts/run_sanity_checks.sh
```

This script byte-compiles all Python microservices and, when Docker Compose is available, validates
both Compose stacks. It provides a quick confirmation that the merged branch is in a good state
before you run the heavier Docker-based end-to-end tests described in each architecture’s README.

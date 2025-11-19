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

3. **Two-Phase Commit Demo (Python / gRPC)**
   - Located in `two_phase_commit/`.
   - Demonstrates a basic 2PC workflow with a coordinator, two voting participants, and a demo client driving transactions over gRPC.
   - Includes Docker Compose that launches the participants, exposes both the voting and decision services on separate ports, and runs a client container that triggers a sample transaction to show commit/abort tracing.

## How to Run
To execute either implementation:

1. Navigate to the corresponding project folder:
   - `cd REST-Server-Client`
   - `cd ecommerce-order-system`
   - `cd two_phase_commit`

2. Open the respective `README.md` file inside that folder.
   Each README provides detailed steps to **build, run, and test** the system.

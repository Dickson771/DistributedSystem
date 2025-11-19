
This file describes steps needed to run a simple microservice architecture based ordering system supported by gRPC communication protocol. User will need to have gRPC, Python,docker engine running to run this application. The following are the steps to run a simple e-commerce system containerized on docker engine.

Step 1: Clone the project files from https://github.com/nebimal/DistributedSystem/tree/main/gRPC-MicroService or images from docker repositories (add image path later)

# Build and start all services
Step 2: Run docker-compose up -d --build 

 # Access the client container
Step 3: Run docker exec -it ecommerce-order-system-client-1 bash

# Run the client application
Step 4: Run python client.py

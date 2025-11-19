FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY protos ./protos
COPY generate_protos.py ./
RUN python generate_protos.py

COPY node.py run_twopc.py .
COPY generated ./generated

ENV NODE_ID=node1 \
    ADDRESS=0.0.0.0:50051 \
    PEERS=""

CMD ["python", "node.py"]

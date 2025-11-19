FROM python:3.11-slim

WORKDIR /app

COPY two_phase_commit/protos /app/two_phase_commit/protos
COPY two_phase_commit/coordinator /app/two_phase_commit/coordinator
COPY two_phase_commit/client /app/two_phase_commit/client
COPY two_phase_commit/__init__.py /app/two_phase_commit/__init__.py

RUN pip install --no-cache-dir -r two_phase_commit/client/requirements.txt

ENV PYTHONPATH=/app

ENTRYPOINT ["/bin/bash", "two_phase_commit/client/entrypoint.sh"]

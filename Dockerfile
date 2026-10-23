FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash curl git iproute2 procps \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir mcp==1.30.0

WORKDIR /app
COPY server.py /app/server.py
COPY .agents /app/.agents
COPY skills /app/skills

ENV HOME=/home/cash MORTAL_BIND_HOST=0.0.0.0
EXPOSE 18765
CMD ["python3", "/app/server.py"]

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install required packages:
# - python3: UDP client/server scripts
# - iproute2: tc command for network emulation
# - iputils-ping: connectivity testing
# - tcpdump: optional packet capture
# - jq: JSON parsing (used by scripts)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    iproute2 \
    iputils-ping \
    tcpdump \
    jq \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /var/log /tmp /artifacts


COPY testbed/app/ /app/

COPY mosh/ /app/mosh/

RUN chmod +x /app/*.sh /app/*.py

WORKDIR /app
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir -r mosh/requirements.txt

# Entrypoint launches server or client based on ROLE env var
ENTRYPOINT ["/app/run_app.sh"]

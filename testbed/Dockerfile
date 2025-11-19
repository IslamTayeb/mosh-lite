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
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /var/log /tmp /artifacts

# Copy mosh library and application
COPY mosh/ /app/mosh/
COPY testbed/app/ /app/
RUN chmod +x /app/*.sh /app/*.py

# Install Python dependencies for mosh
RUN pip3 install --no-cache-dir -r /app/mosh/requirements.txt --break-system-packages

WORKDIR /app

# Entrypoint launches server or client based on ROLE env var
ENTRYPOINT ["/app/run_app.sh"]

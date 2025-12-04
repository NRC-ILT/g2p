# Dockerfile to run g2p studio, production style, in a container
# Build: docker build -t g2p .
# Run: docker run -p 8000:8000 g2p

# Base Image
FROM debian:latest

ENV DEBIAN_FRONTEND=noninteractive

# Dependencies that don't change with g2p updates and can be cached, and make it lean
RUN apt-get update -y \
    && apt-get install -y \
        apt-transport-https \
        libffi-dev \
        openssl \
        libssl-dev \
        python3 \
        python3-pip \
        python3-dev \
        python3-venv \
        build-essential \
        nano \
        git \
    && apt-get clean \
    && apt-get autoremove \
    && rm -fr /var/lib/apt/lists/*

# Create a venv to install packages locally
RUN python3 -m venv --system-site-packages /g2p/venv

# Get g2p-specific dependencies that can also often be cached
RUN mkdir -p /g2p/g2p
COPY requirements.txt /g2p
COPY pyproject.toml /g2p
RUN . /g2p/venv/bin/activate \
    && python3 -m pip install --upgrade pip \
    && MAKEFLAGS="-j$(nproc)" pip3 install -r /g2p/requirements.txt

# Install g2p itself, last
COPY . /g2p/
COPY README.md /g2p
COPY Dockerfile /g2p
RUN . /g2p/venv/bin/activate \
    && SETUPTOOLS_SCM_PRETEND_VERSION=$(cat g2p/.SETUPTOOLS_SCM_PRETEND_VERSION) pip3 install -e /g2p

# Comment this out if you just want to install g2p in the container without running the studio.
CMD . /g2p/venv/bin/activate && gunicorn --worker-class uvicorn.workers.UvicornWorker -w 1 g2p.app:APP --bind 0.0.0.0:8000

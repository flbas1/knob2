FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

# Install Node.js
RUN apt-get update && \
    apt-get install -y curl git && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y nodejs

# Install OpenCode
RUN npm install -g opencode-ai

# Python packages
# COPY requirements.txt /tmp/

# RUN if [ -f /tmp/requirements.txt ]; then \
#         pip install --no-cache-dir -r /tmp/requirements.txt; \
#     fi

WORKDIR /workspace
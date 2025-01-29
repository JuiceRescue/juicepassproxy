FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.source=https://github.com/JuiceRescue/juicepassproxy

ENV DEBUG=false

RUN pip install --root-user-action=ignore --no-cache-dir --upgrade pip
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y tini git curl
RUN mkdir -p /juicepassproxy
RUN mkdir -p /log
RUN mkdir -p /config
COPY * /juicepassproxy
RUN pip install --root-user-action=ignore --no-cache-dir -r /juicepassproxy/requirements.txt
RUN chmod -f +x /juicepassproxy/*.sh

ENTRYPOINT ["/usr/bin/tini", "--", "/juicepassproxy/docker_entrypoint.sh"]

FROM python:3.12-slim-bookworm
# WARNING: Do not update python past 3.12.* if telnetlib is still being used.

LABEL org.opencontainers.image.source=https://github.com/snicker/juicepassproxy

ENV DEBUG=false
ENV UPDATE_UDPC=false

RUN pip install --upgrade pip
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y git curl
RUN git clone https://github.com/snicker/juicepassproxy.git /juicepassproxy
RUN pip install --no-cache-dir -r /juicepassproxy/requirements.txt
RUN chmod -f +x /juicepassproxy/*.sh

ENTRYPOINT /juicepassproxy/docker_entrypoint.sh

FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.source=https://github.com/snicker/juicepassproxy

ENV MQTT_HOST="127.0.0.1"
ENV MQTT_PORT=1883
ENV MQTT_DISCOVERY_PREFIX="homeassistant"
ENV DEVICE_NAME="JuiceBox"
ENV DEBUG=false

RUN pip install --upgrade pip
RUN apt-get update && apt-get install -y gnupg curl
RUN echo "deb https://ppa.launchpadcontent.net/rmescandon/yq/ubuntu jammy main" > /etc/apt/sources.list.d/yq.list
RUN echo "deb-src https://ppa.launchpadcontent.net/rmescandon/yq/ubuntu jammy main" >> /etc/apt/sources.list.d/yq.list
RUN curl -sS 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x9a2d61f6bb03ced7522b8e7d6657dbe0cc86bb64' | gpg --dearmor | tee /etc/apt/trusted.gpg.d/yq.gpg
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y git dnsutils net-tools telnet expect yq
RUN git clone https://github.com/snicker/juicepassproxy.git /juicepassproxy
RUN pip install --no-cache-dir -r /juicepassproxy/requirements.txt
RUN chmod +x /juicepassproxy/*.sh /juicepassproxy/*.expect

ENTRYPOINT /juicepassproxy/docker_entrypoint.sh

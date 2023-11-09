FROM python:3.12-slim-bookworm

ENV MQTT_HOST="127.0.0.1"
ENV MQTT_PORT=1883
ENV MQTT_DISCOVERY_PREFIX="homeassistant"
ENV DEVICE_NAME="JuiceBox"
ENV ENELX_PORT=8047
ENV ENELX_SERVER="juicenet-udp-prod3-usa.enelx.com"
ENV SRC_DEFAULT="127.0.0.1"
ENV DST_DEFAULT="54.161.147.91"
ENV DEBUG=false

RUN pip install --upgrade pip
RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install -y git curl dnsutils net-tools telnet expect
# RUN apt-get install -y iputils-ping netcat-traditional nano # Used for debugging
RUN git clone https://github.com/snicker/juicepassproxy.git /juicepassproxy
RUN pip install --no-cache-dir -r /juicepassproxy/requirements.txt

ENTRYPOINT /juicepassproxy/docker_entrypoint.sh

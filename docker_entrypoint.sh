#!/bin/bash

JUICEPASSPROXY="/juicepassproxy/juicepassproxy.py"

function logger() {
  if [ "${1^^}" != "DEBUG" ] || ($DEBUG && [ "${1^^}" = "DEBUG" ]); then
    printf "%-15s %-10s %s\n" "$(date +'%Y-%m-%d %H:%M:%S,%3N')" "${1^^}" "${2}"
  fi
}

echo "--------------------------------"
logger INFO "Starting JuicePass Proxy"
echo ""

JPP_STRING="python3 ${JUICEPASSPROXY}"
logger INFO "Docker Environment Variables:"
if [[ ! -z "${DEVICE_NAME}" ]]; then
  logger INFO "DEVICE_NAME: ${DEVICE_NAME}"
  JPP_STRING+=" --name ${DEVICE_NAME}"
fi
if [[ ! -z "${JUICEBOX_HOST}" ]]; then
  logger INFO "JUICEBOX_HOST: ${JUICEBOX_HOST}"
  JPP_STRING+=" --juicebox_host ${JUICEBOX_HOST}"
fi
if [[ ! -z "${JUICEBOX_ID}" ]]; then
  logger INFO "JUICEBOX_ID: ${JUICEBOX_ID}"
  JPP_STRING+=" --juicebox_id ${JUICEBOX_ID}"
fi
if [[ ! -z "${SRC}" ]]; then
  logger INFO "SRC: ${SRC}"
  JPP_STRING+=" --src ${SRC}"
fi
if [[ ! -z "${DST}" ]]; then
  logger INFO "DST: ${DST}"
  JPP_STRING+=" --dst ${DST}"
fi
if [[ ! -z "${MQTT_HOST}" ]]; then
  logger INFO "MQTT_HOST: ${MQTT_HOST}"
  JPP_STRING+=" --mqtt_host ${MQTT_HOST}"
fi
if [[ ! -z "${MQTT_PORT}" ]]; then
  logger INFO "MQTT_PORT: ${MQTT_PORT}"
  JPP_STRING+=" --mqtt_port ${MQTT_PORT}"
fi
if [[ ! -z "${MQTT_USER}" ]]; then
  logger INFO "MQTT_USER: ${MQTT_USER}"
  JPP_STRING+=" --mqtt_user ${MQTT_USER}"
fi
if [[ ! -z "${MQTT_PASS}" ]]; then
  logger INFO "MQTT_PASS: $(echo ${MQTT_PASS} | sed -E 's/./*/g')"
  JPP_STRING+=" --mqtt_password ${MQTT_PASS}"
fi
if [[ ! -z "${MQTT_DISCOVERY_PREFIX}" ]]; then
  logger INFO "MQTT_DISCOVERY_PREFIX: ${MQTT_DISCOVERY_PREFIX}"
  JPP_STRING+=" --mqtt_discovery_prefix ${MQTT_DISCOVERY_PREFIX}"
fi
if [[ ! -z "${JPP_HOST}" ]]; then
  logger INFO "JPP_HOST: ${JPP_HOST}"
  JPP_STRING+=" --juicepass_proxy_host ${JPP_HOST}"
fi
logger INFO "UPDATE_UDPC: ${UPDATE_UDPC}"
if $UPDATE_UDPC; then
  JPP_STRING+=" --update_udpc"
fi
if [[ ! -z "${UDPC_TIMEOUT}" ]]; then
  logger INFO "UDPC_TIMEOUT: ${UDPC_TIMEOUT}" 
  JPP_STRING+=" --udpc_timeout ${UDPC_TIMEOUT}"
fi
JPP_STRING+=" --config_loc /config"
logger INFO "DEBUG: ${DEBUG}"
if $DEBUG; then
  JPP_STRING+=" --debug"
fi

logger DEBUG "COMMAND: $(echo ${JPP_STRING} | sed -E 's/(.* --mqtt_password )([\"]?[a-zA-Z0-9_\?\*\^\&\#\@\!]+[\"]?)/\1*****/g')"
eval ${JPP_STRING}

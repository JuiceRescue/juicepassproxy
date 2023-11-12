#!/bin/bash

CONFIG_FILE="/config/juicepassproxy.yaml"
JUICEPASSPROXY="/juicepassproxy/juicepassproxy.py"
TELNET_GET_SERVER="/juicepassproxy/telnet_get_server.expect"
TELNET_GET_JUICEBOX_ID="/juicepassproxy/telnet_get_juicebox_id.expect"

ENELX_PORT_DEFAULT="8047"
ENELX_SERVER_DEFAULT="juicenet-udp-prod3-usa.enelx.com"
SRC_DEFAULT="127.0.0.1"
DST_DEFAULT="54.161.147.91"

RED='\033[1;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

function logger() {
  if [ "${1^^}" != "DEBUG" ] || ($DEBUG && [ "${1^^}" = "DEBUG" ]); then
    if [ "${1^^}" = "ERROR" ]; then
      printf "%-15s ${RED}%-10s %s${NC}\n" "$(date +'%Y-%m-%d %H:%M:%S')" "${1^^}" "${2}"
    elif [ "${1^^}" = "WARNING" ]; then
      printf "%-15s ${YELLOW}%-10s %s${NC}\n" "$(date +'%Y-%m-%d %H:%M:%S')" "${1^^}" "${2}"
    else
      printf "%-15s %-10s %s\n" "$(date +'%Y-%m-%d %H:%M:%S')" "${1^^}" "${2}"
    fi
  fi
}

function valid_ip() {
    local  ip=$1
    local  stat=1

    if [[ $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        OIFS=$IFS
        IFS='.'
        ip=($ip)
        IFS=$OIFS
        [[ ${ip[0]} -le 255 && ${ip[1]} -le 255 \
            && ${ip[2]} -le 255 && ${ip[3]} -le 255 ]]
        stat=$?
    fi
    return $stat
}

echo "--------------------------------"
logger info "Starting JuicePass Proxy"
echo ""
logger INFO "DEBUG: ${DEBUG}"

if test -f ${CONFIG_FILE}; then
  logger DEBUG  "Importing Config File"
  JUICEBOX_ID_CONFIG="$(yq e '.JUICEBOX_ID' ${CONFIG_FILE})"
  if [[ "${JUICEBOX_ID_CONFIG}" = "null" ]]; then
    unset JUICEBOX_ID_CONFIG
  fi
  ENELX_SERVER_CONFIG="$(yq e '.ENELX_SERVER' ${CONFIG_FILE})"
  if [[ "${ENELX_SERVER_CONFIG}" = "null" ]]; then
    unset ENELX_SERVER_CONFIG
  fi
  ENELX_PORT_CONFIG="$(yq e '.ENELX_PORT' ${CONFIG_FILE})"
  if [[ "${ENELX_PORT_CONFIG}" = "null" ]]; then
    unset ENELX_PORT_CONFIG
  fi
  SRC_CONFIG="$(yq e '.SRC' ${CONFIG_FILE})"
  if [[ "${SRC_CONFIG}" = "null" ]]; then
    unset SRC_CONFIG
  fi
  DST_CONFIG="$(yq e '.DST' ${CONFIG_FILE})"
  if [[ "${DST_CONFIG}" = "null" ]]; then
    unset DST_CONFIG
  fi
else
  logger DEBUG "No Config File Found."
fi

if [[ ! -z "${JUICEBOX_LOCAL_IP}" ]]; then
  if [[ -z "${JUICEBOX_ID}" ]]; then
    JUICEBOX_ID=$(${TELNET_GET_JUICEBOX_ID} ${JUICEBOX_LOCAL_IP} | sed -n 8p)
    if [[ ! -z "${JUICEBOX_ID}" ]]; then
      logger DEBUG "Sucessfully obtained JuiceBox ID."
      JUICEBOX_ID=${JUICEBOX_ID%?}
    elif [[ ! -z "${JUICEBOX_ID_CONFIG}" ]]; then
      logger WARNING "Cannot get JuiceBox ID. Using config."
      JUICEBOX_ID=${JUICEBOX_ID_CONFIG}
    else
      echo -e "\n${RED}******************************************************************************${NC}"
      logger ERROR "Cannot get JuiceBox ID from Telnet. If a JuiceBox ID is later set or is obtained via Telnet, it will likely create a new JuiceBox Device with new Entities in Home Assistant."
      echo -e "${RED}******************************************************************************${NC}\n"
      unset JUICEBOX_ID
    fi
  fi

  TELNET_SERVER_STRING=$(${TELNET_GET_SERVER} ${JUICEBOX_LOCAL_IP} | grep "UDPC")
  if [[ ! -z "${TELNET_SERVER_STRING}" ]]; then
    logger DEBUG "Sucessfully obtained EnelX Server and Port."
    #logger debug "TELNET_SERVER_STRING: ${TELNET_SERVER_STRING}"
    ENELX_SERVER=$(echo ${TELNET_SERVER_STRING} | sed -E 's/(# 2 UDPC[ ]+)(.*)(:.*)/\2/g')
    ENELX_PORT=$(echo ${TELNET_SERVER_STRING} | sed -E 's/(.*:)(.*)([ ]+.*)/\2/g')
  else
    if [[ ! -z "${ENELX_SERVER_CONFIG}" ]]; then
      logger WARNING "Cannot get EnelX Server from Telnet. Using config."
      ENELX_SERVER=${ENELX_SERVER_CONFIG}
    else
      logger ERROR "Cannot get EnelX Server from Telnet. Not set in config. Using default."
      ENELX_SERVER=${ENELX_SERVER_DEFAULT}
    fi
    if [[ ! -z "${ENELX_PORT_CONFIG}" ]]; then
      logger WARNING "Cannot get EnelX Port from Telnet. Using config."
      ENELX_PORT=${ENELX_PORT_CONFIG}
    else
      logger ERROR "Cannot get EnelX Port from Telnet. Not set in config. Using default."
      ENELX_PORT=${ENELX_PORT_DEFAULT}
    fi
  fi
else
  logger DEBUG "JuiceBox Local IP not defined."
fi

if [[ -z "${SRC}" ]]; then
  SRC=$(ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p')
  if valid_ip ${SRC}; then
    logger DEBUG "Sucessfully obtained Docker Local IP."
  elif [[ ! -z "${SRC_CONFIG}" ]]; then
    logger WARNING "Cannot get Docker Local IP. Using config."
    SRC=${SRC_CONFIG}
  else
    logger ERROR "Cannot get Docker Local IP. Not set in config. Using default."
    SRC=${SRC_DEFAULT}
  fi
fi

if [[ -z "${DST}" ]]; then
  DST=$(dig +short @1.1.1.1 ${ENELX_SERVER} | awk '{ getline ; print $1 ; exit }')
  if valid_ip ${DST}; then
    logger DEBUG "Sucessfully obtained EnelX Server IP."
  elif [[ ! -z "${DST_CONFIG}" ]]; then
    logger WARNING "Cannot get EnelX Server IP. Using config."
    DST=${DST_CONFIG}
  else
    logger ERROR "Cannot get EnelX Server IP. Not set in config. Using default."
    DST=${DST_DEFAULT}
  fi
fi

JPP_STRING="python3 ${JUICEPASSPROXY} --src ${SRC}:${ENELX_PORT} --dst ${DST}:${ENELX_PORT} --host ${MQTT_HOST} --port ${MQTT_PORT} --discovery-prefix ${MQTT_DISCOVERY_PREFIX} --name ${DEVICE_NAME}"
echo ""
logger INFO "DEVICE_NAME: ${DEVICE_NAME}"
logger INFO "JUICEBOX_LOCAL_IP: ${JUICEBOX_LOCAL_IP}"
if [[ ! -z "${JUICEBOX_ID}" ]]; then
  logger INFO "JUICEBOX_ID: ${JUICEBOX_ID}"
  JPP_STRING+=" --juicebox-id ${JUICEBOX_ID}"
fi

logger INFO "SRC: ${SRC}"
logger INFO "DST: ${DST}"
logger INFO "ENELX_SERVER: ${ENELX_SERVER}"
logger INFO "ENELX_PORT: ${ENELX_PORT}"
logger INFO "MQTT_HOST: ${MQTT_HOST}"
logger INFO "MQTT_PORT: ${MQTT_PORT}"
if [[ ! -z "${MQTT_USER}" ]]; then
  logger INFO "MQTT_USER: ${MQTT_USER}"
  JPP_STRING+=" --user ${MQTT_USER}"
fi
if [[ ! -z "${MQTT_PASS}" ]]; then
  logger INFO "MQTT_PASS: $(echo ${MQTT_PASS} | sed -E 's/./*/g')"
  JPP_STRING+=" --password ${MQTT_PASS}"
fi

logger INFO "MQTT_DISCOVERY_PREFIX: ${MQTT_DISCOVERY_PREFIX}"

if $DEBUG; then
  JPP_STRING+=" --debug"
fi

touch ${CONFIG_FILE}
if [[ ! -z "${JUICEBOX_ID}" ]]; then
  eval "yq e -i '.JUICEBOX_ID = \"${JUICEBOX_ID}\"' ${CONFIG_FILE}"
fi
if [[ ! -z "${ENELX_SERVER}" ]]; then
  eval "yq e -i '.ENELX_SERVER = \"${ENELX_SERVER}\"' ${CONFIG_FILE}"
fi
if [[ ! -z "${ENELX_PORT}" ]]; then
  eval "yq e -i '.ENELX_PORT = \"${ENELX_PORT}\"' ${CONFIG_FILE}"
fi
if [[ ! -z "${SRC}" ]]; then
  eval "yq e -i '.SRC = \"${SRC}\"' ${CONFIG_FILE}"
fi
if [[ ! -z "${DST}" ]]; then
  eval "yq e -i '.DST = \"${DST}\"' ${CONFIG_FILE}"
fi
if $DEBUG; then
  echo -e "\n${CYAN}${CONFIG_FILE}:${NC}"
  yq e /config/juicepassproxy.yaml
  echo ""
fi
logger INFO "COMMAND: $(echo ${JPP_STRING} | sed -E 's/(--password )(\<.*\>)(.*)/\1*****\3/')"
eval ${JPP_STRING}

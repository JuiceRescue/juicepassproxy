#!/bin/bash

NOW=$(date +'%x %X')

echo "--------------------------------"
echo "${NOW}: Starting JuicePassProxy"
echo ""

if [ ! -z "${JUICEBOX_LOCAL_IP+x}" ]; then
  echo "${NOW}: JUICEBOX_LOCAL_IP: ${JUICEBOX_LOCAL_IP}"
  TELNET_STRING=$(/juicepassproxy/telnet_get_server.expect ${JUICEBOX_LOCAL_IP} | grep "UDPC")
  retval=$?
  if [ ${retval} -eq 0 ]; then
    #echo "${NOW}: TELNET_STRING: ${TELNET_STRING}"
    ENELX_SERVER=$(echo ${TELNET_STRING} | sed -E 's/(^.*[0-9]+.*UDPC[ ]+)(.*)(:.*)/\2/g')
    #echo "${NOW}: ENELX_SERVER: ${ENELX_SERVER}"
    ENELX_PORT=$(echo ${TELNET_STRING} | sed -E 's/(^.*:)(.*)([ ]+.*)/\2/g')
    #echo "${NOW}: ENELX_PORT: ${ENELX_PORT}"
  else
    echo "ERROR getting EnelX Server from Telnet. Using defaults."
  fi
fi
if [ -z "${SRC+x}" ]; then
  SRC=$(ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p')
  retval=$?
  if [ ${retval} -ne 0 ]; then
    echo "ERROR getting Docker Local IP. Using default."
    SRC=${SRC_DEFAULT}
  fi
fi

if [ -z "${DST+x}" ]; then
  DST=$(dig +short @1.1.1.1 ${ENELX_SERVER} | awk '{ getline ; print $1 ; exit }')
  retval=$?
  if [ ${retval} -ne 0 ]; then
    echo "ERROR getting EnelX Server IP. Using default."
    DST=${DST_DEFAULT}
  fi
fi

JPP_STRING="python /juicepassproxy/juicepassproxy.py --src ${SRC}:${ENELX_PORT} --dst ${DST}:${ENELX_PORT} --host ${MQTT_HOST} --port ${MQTT_PORT} --discovery-prefix ${MQTT_DISCOVERY_PREFIX} --name ${DEVICE_NAME}"

echo "${NOW}: SRC: ${SRC}"
echo "${NOW}: DST: ${DST}"
echo "${NOW}: ENELX_SERVER: ${ENELX_SERVER}"
echo "${NOW}: ENELX_PORT: ${ENELX_PORT}"
echo "${NOW}: MQTT_HOST: ${MQTT_HOST}"
echo "${NOW}: MQTT_PORT: ${MQTT_PORT}"
if [ ! -z "${MQTT_USER+x}" ]; then
  echo "${NOW}: MQTT_USER: ${MQTT_USER}"
  JPP_STRING+=" --user ${MQTT_USER}"
fi
if [ ! -z "${MQTT_PASS+x}" ]; then
  echo "${NOW}: MQTT_PASS: $(echo ${MQTT_PASS} | sed -E 's/./*/g')"
  JPP_STRING+=" --password ${MQTT_PASS}"
fi
echo "${NOW}: MQTT_DISCOVERY_PREFIX: ${MQTT_DISCOVERY_PREFIX}"
echo "${NOW}: DEVICE_NAME: ${DEVICE_NAME}"
echo "${NOW}: DEBUG: ${DEBUG}"

if [ "${DEBUG}" = true ] ; then
  JPP_STRING+=" --debug"
fi

echo "${NOW}: COMMAND: $(echo ${JPP_STRING} | sed -E 's/(--password )(\<.*\>)(.*)/\1*****\3/')"
eval ${JPP_STRING}

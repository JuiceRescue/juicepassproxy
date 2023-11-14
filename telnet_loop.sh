#!/bin/bash

while true
do
  /juicepassproxy/telnet_update_udpc.expect ${1} ${2}
  sleep 10
done

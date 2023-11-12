# JuicePass Proxy

This tool will publish JuiceBox data by using a Man in the Middle UDP proxy to MQTT that is auto-discoverable by HomeAssistant. The `Enel X Way` app will continue to function.

Builds upon work by lovely folks in this issue: https://github.com/home-assistant/core/issues/86588

_Hopefully we won't need this if EnelX fixes their API!_

#### It is required that both your JuiceBox and the machine you are running `juicepassproxy` on have internal static IPs on your intranet.

## Docker Compose Installation

### Features
*  If JuiceBox Local IP is defined, it will run a telnet script to get the EnelX Server and Port.

*  If DST is not defined, it will use `dig` with the CloudFlare DNS (1.1.1.1) to get the IP address of the EnelX Server and avoid a DNS lookup loop.

*  If SRC is not defined, it will use `ifconfig` to get the Local IP address of the Docker.

### Instructions

1. Configure your DNS server running on your network (like Pi-hole or your router) to route all UDP traffic from your JuiceBox to the machine running this proxy. Instructions for how to do this will vary by router. See [Getting EnelX Server IPs](#getting-enelx-server-ips) for instructions on what EnelX Server you need to override.

1. Add the `juicepassproxy` service to your Docker Compose file.

    A.  Set `ports:` to the port listed in the UDCP line _(see [Getting EnelX Server IPs](#getting-enelx-server-ips))_.

    B. Define the applicable environment variables _(see [Docker Environment Variables](#docker-environment-variables))_.

1. Start the Docker container.

### Example Docker Compose

```yaml
version: '3.8'

networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 172.16.100.0/24

services:
  juicepassproxy:
    image: ghcr.io/snicker/juicepassproxy:latest
    hostname: juicepassproxy
    container_name: juicepassproxy
    restart: unless-stopped
    logging:
      driver: json-file
    ports:
      - 8047:8047/udp
    environment:
      - JUICEBOX_LOCAL_IP=10.100.50.30
      - MQTT_HOST=10.100.200.5
      - MQTT_USER=mosquitto
      - MQTT_PASS=***
    volumes:
      - /etc/localtime:/etc/localtime:ro
```

### Docker Environment Variables

Variable | Required | Description & Default |
-- | -- | --
**JUICEBOX_LOCAL_IP** | **Recommended** | If defined, it will attempt to get the EnelX Server and Port using Telnet. If unsuccessful, it will default to the EnelX Server and Port below.
**SRC** | No | If not defined, it will attempt to get the Local Docker IP. If unsuccessful, it will default to 127.0.0.1.
**DST** | No | If not defined, it will attempt to get the IP of the EnelX Server. If unsuccessful, it will default to 54.161.185.130. If manually defined, you should only use the IP address of the EnelX Server and not the fully qualified domain name to avoid DNS lookup loops.
**ENELX_SERVER** | No | juicenet-udp-prod3-usa.enelx.com
**ENELX_PORT** | No | 8047
**MQTT_HOST** | No | 127.0.0.1
**MQTT_PORT** | No | 1883
**MQTT_USER** | No |
**MQTT_PASS** | No |
**MQTT_DISCOVERY_PREFIX** | No | homeassistant
**DEVICE_NAME** | No | JuiceBox
**DEBUG** | No | false


<details>
<summary><h2>Manual Installation</h2></summary>

1. Clone this repository
2. Use Python 3.10+ (I recommend setting up a virtual environment)
3. Install requirements `pip install -r requirements.txt`
4. Launch by executing `python juicepassproxy.py --dst <enelx IP:port> --host <mqtthost>` (params documented below)
5. Nothing happens!
6. Configure your DNS server running on your network (like Pi-hole or your router) to route all DNS requests from EnelX to the machine running this proxy. For me this was `juicenet-udp-prod3-usa.enelx.com`. See below for instructions to determine that.

### CLI Options

```
options:
  -h, --help            show this help message and exit
  -s SRC, --src SRC     Source IP and port, (default: 127.0.0.1:8047)
  -d DST, --dst DST     Destination IP and port of EnelX Server.
  --debug
  -u USER, --user USER  MQTT username
  -P PASSWORD, --password PASSWORD
                        MQTT password
  -H HOST, --host HOST  MQTT hostname to connect to (default: 127.0.0.1)
  -p PORT, --port PORT  MQTT port (default: 1883)
  -D DISCOVERY_PREFIX, --discovery-prefix DISCOVERY_PREFIX
                        Home Assistant MQTT topic prefix (default: homeassistant)
  --name DEVICE_NAME    Home Assistant Device Name (default: Juicebox)
```

_For **DST**, you should only use the IP address of the EnelX Server and **not** the fully qualified domain name (FQDN) to avoid DNS lookup loops._

</details>

## Getting EnelX Server IPs

To get the destination IP:Port of the EnelX server, telnet to your Juicenet device:
`$ telnet 192.168.x.x 2000`
and type the `list` command:

```
list
! # Type  Info
# 0 FILE  webapp/index.html-1.4.0.24 (1995, 0)
# 1 UDPC  juicenet-udp-prod3-usa.enelx.com:8047 (26674)
```

The address is in the `UDPC` line. Run, `ping`, `nslookup`, or similar command to determine the IP.

As of November, 2023: `juicenet-udp-prod3-usa.enelx.com` = `54.161.185.130`.

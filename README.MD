# JuicePass Proxy

This tool will publish JuiceBox data by using a Man in the Middle UDP proxy to MQTT that is auto-discoverable by HomeAssistant. The `Enel X Way` app will continue to function.

It can also publish the IP of the proxy to the JuiceBox directly to avoid using custom local DNS servers using the `update_udpc` and `juicebox_host` command line parameters.

Builds upon work by lovely folks in this issue: https://github.com/home-assistant/core/issues/86588

_Hopefully we won't need this if EnelX fixes their API!_

#### It is required that both your JuiceBox and the machine you are running `juicepassproxy` on have internal static IPs on your intranet.

## Docker Compose Installation

### Features
*  If JuiceBox Local IP is defined, it will run a telnet script to get the EnelX Server and Port as well as the JuiceBox ID.

*  If DST is not defined, it will use `dig` with the CloudFlare DNS (1.1.1.1) to get the IP address of the EnelX Server and avoid a DNS lookup loop.

*  If SRC is not defined, it will use `ifconfig` to get the Local IP address of the Docker.

* If Update UDPC is true, JuicePass Proxy will continually update the JuiceBox via telnet to send its data to JuicePass Proxy. Use this if you are not able to change your DNS to route the JuiceBox traffic to JuicePass Proxy.

### Instructions

1. Pick One Option:

    A. Configure your DNS server running on your network (like Pi-hole or your router) to route all UDP traffic from your JuiceBox to the machine running this proxy. Instructions for how to do this will vary by router. See [Getting EnelX Server IPs](#getting-enelx-server-ips) for instructions on what EnelX Server you need to override.

    B. Set these Docker Environment Variables in your Docker Compose file:</br>
      ```
      UPDATE_UDPC=true
      JUICEBOX_HOST=<IP address of your JuiceBox>
      JPP_HOST=<IP address of the machine that the JuicePass Proxy Docker Container is running on>
      ```

1. Add the `juicepassproxy` service to your Docker Compose file.

    A.  Set `ports:` to the port listed in the UDCP line _(see [Getting EnelX Server IPs](#getting-enelx-server-ips))_.

    B. Define the applicable environment variables _(see [Docker Environment Variables](#docker-environment-variables))_.

    C. Specify the location for the config folder

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
      - JUICEBOX_HOST=10.100.50.30
      - UPDATE_UDPC=true
      - JPP_HOST=10.100.200.50
      - MQTT_HOST=10.100.200.5
      - MQTT_USER=mosquitto
      - MQTT_PASS=***
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - ./config:/config
```

### Docker Environment Variables

Variable | Required | Description & Default |
-- | -- | --
**JUICEBOX_HOST** | **Recommended**</br></br>**Required if Update UDPC is True.** | If defined, it will attempt to get the EnelX Server and Port using Telnet. If unsuccessful, it will default to the EnelX Server and Port below.
**UPDATE_UDPC** | No | Default: false. If true, will continually update the JuiceBox via telnet to point to JuicePass Proxy.
**JPP_HOST**  | **Required if Update UDPC is True** |  This is the IP or Hostname of the machine where JuicePass Proxy is running (**not** the IP of the Docker Container)
**SRC** | No | If not defined, it will attempt to get the Local Docker IP. If unsuccessful, it will default to 127.0.0.1.
**DST** | No | If not defined, it will attempt to get the IP of the EnelX Server. If unsuccessful, it will default to 54.161.185.130. If manually defined, you should only use the IP address of the EnelX Server and not the fully qualified domain name to avoid DNS lookup loops.
**JUICEBOX_ID**  | No | If not defined, it will attempt to get the JuiceBox ID using Telnet.  
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
2. Use Python 3.10-3.12 (I recommend setting up a virtual environment)
3. Install requirements `pip install -r requirements.txt`
4. Launch by executing `python3 juicepassproxy.py --juicebox_host <IP of the JuiceBox> --mqtt_host <mqtt_host>` (params documented below)
5. Nothing happens!
6. Configure your DNS server running on your network (like Pi-hole or your router) to route all DNS requests from EnelX to the machine running this proxy. For me this was `juicenet-udp-prod3-usa.enelx.com`. See below for instructions to determine that.
7. Alternatively to #6, you can enable `update_udpc` on the command line and set `juicebox_host` and the application will force publish the IP in the `src` argument to the Juicebox and avoid the need to set DNS rules on your router or DNS server. **NOTE: if you need to publish a different IP than the one in the `src` argument, you can make use of the `--juicepass_proxy_host` arg.**

### CLI Options

```
options:
  -h, --help            show this help message and exit
  -s SRC, --src SRC     Source IP (and optional port). If not defined, will
                        obtain it automatically. (Ex. 127.0.0.1:8047)
  -d DST, --dst DST     Destination IP (and optional port) of EnelX Server. If
                        not defined, --juicebox_host required and then will
                        obtain it automatically. (Ex. 127.0.0.1:8047)
  --debug
  -u MQTT_USER, --mqtt_user MQTT_USER
                        MQTT Username
  -P MQTT_PASSWORD, --mqtt_password MQTT_PASSWORD
                        MQTT Password
  -H MQTT_HOST, --mqtt_host MQTT_HOST
                        MQTT Hostname to connect to (default: 127.0.0.1)
  -p MQTT_PORT, --mqtt_port MQTT_PORT
                        MQTT Port (default: 1883)
  -D MQTT_DISCOVERY_PREFIX, --mqtt_discovery_prefix MQTT_DISCOVERY_PREFIX
                        Home Assistant MQTT topic prefix (default:
                        homeassistant)
  --name DEVICE_NAME    Home Assistant Device Name (default: JuiceBox)
  --juicebox_id JUICEBOX_ID
                        JuiceBox ID. If not defined, will obtain it
                        automatically.
  --update_udpc         Update UDPC on the JuiceBox. Requires --juicebox_host
  --juicebox_host JUICEBOX_HOST
                        Host or IP address of the JuiceBox. Required for
                        --update_udpc or if --dst not defined.
  --juicepass_proxy_host JUICEPASS_PROXY_HOST
                        EXTERNAL host or IP address of the machine running
                        JuicePass Proxy. Optional: only necessary when using
                        --update_udpc and it will be inferred from the address
                        in --src if omitted.
  --config_loc CONFIG_LOC
                        The location to store the config file (default:
                        /~/.juicepassproxy)
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

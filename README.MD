# Juicepass Proxy

Builds upon some work by lovely folks in this issue:

https://github.com/home-assistant/core/issues/86588

This tool will publish Juicebox data from a UDP proxy to MQTT discoverable by HomeAssistant.

Hopefully we won't need this if EnelX fixes their API!

## Installation

1. Clone this repository
2. Use Python 3.10+ (I recommend setting up a virtual environment)
3. Install requirements `pip install -r requirements.txt`
4. Launch by executing `python juicepassproxy.py --dst <enelx IP:port> --host <mqtthost>` (params documented below)
5. Nothing happens!
6. Configure your DNS server running on your network (like Pihole! or your router) to route all DNS requests to EnelX to the machine running this proxy. For me this was `juicenet-udp-prod3-usa.enelx.com`. See below for instructions to determine that.

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

### Getting EnelX server IPs

To get the destination IP:Port of the EnelX server, telnet to your Juicenet device:
`$ telnet 192.168.x.x 2000`
and give a `list` command:

```
> list
> ! # Type  Info
> # 0 FILE  webapp/index.html-1.4.0.24 (1995, 0)
> # 1 UDPC  juicenet-udp-prod3-usa.enelx.com:8047 (26674)
```

The address is in the UDPC line- give that an nslookup or other to determine IP
eg juicenet-udp-prod3-usa.enelx.com is currently 54.161.185.130

This may change over time- but if you are using a local DNS server to reroute those requests to this proxy, you should stick to using the IP address here to avoid nameserver lookup loops.


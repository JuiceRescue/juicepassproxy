from pyproxy import pyproxy
import argparse
import logging

AP_DESCRIPTION = """
Juicebox Proxy - 
publish Juicebox data from a UDP proxy to MQTT discoverable by HomeAssistant.

To get the destination IP:Port of the EnelX server, telnet to your Juicenet 
device:
$ telnet 192.168.x.x 2000
and give a `list` command:
> list
> ! # Type  Info
> # 0 FILE  webapp/index.html-1.4.0.24 (1995, 0)
> # 1 UDPC  juicenet-udp-prod3-usa.enelx.com:8047 (26674)
the address is in the UDPC line- give that an nslookup or other to determine IP
juicenet-udp-prod3-usa.enelx.com - 54.161.185.130

this may change over time- but if you are using a local DNS server to reroute 
those requests to this proxy, you should stick to using the IP address here to 
avoid nameserver lookup loops.
"""



def basic_message_try_parse(data):
    """
    juicebox status

    {% set status = states('input_text.juicebox_raw_data').split(",")[5] %}

    {% if status == 'S0' %}
    unplugged
    {% elif status == 'S1' %}
    plugged
    {% elif status == 'S2' %}
    charging
    {% endif %}
    juicebox current

    {% if states('sensor.juicebox_plugged') == 'charging' %}
    {{ states('input_text.juicebox_raw_data').split(",")[16].split("A")[1]|float(default=0) }}
    {% else %}
    0.0
    {% endif %}
    juicebox frequency

    {{ states('input_text.juicebox_raw_data').split(",")[12].split("f")[1]|float(default=0)*0.01 }}

    juicebox lifetime power

    {{ states('input_text.juicebox_raw_data').split(",")[4].split("L")[1]|float(default=0) }}

    juicebox session power


    {% if states('sensor.juicebox_plugged') == 'charging' %}
    {{ states('input_text.juicebox_raw_data').split(",")[15].split("E")[1]|float(default=0) }}
    {% else %}
    0.0
    {% endif %}
    juicebox temperature (i changed to Fahrenheit)

    {{ states('input_text.juicebox_raw_data').split(",")[6].split("T")[1]|float(default=0)*1.8+32 }}

    juicebox voltage

    {{ states('input_text.juicebox_raw_data').split(",")[3].split("V")[1]|float(default=0)*0.1 }}
    """
    message = {'type': 'basic'}
    try:
        parts = str(data).split(',')
        message['status'] = {'S0':'unplugged','S1':'plugged','S2':'charging'}.get(parts[5])
        if message['status'] is None:
            message['status'] = 'unknown {}'.format(parts[5])
        message['current'] = float(parts[16].split('A')[1]) if message['status'] == 'charging' else 0.0
        message['frequency'] = float(parts[12].split('f')[1])*0.01
        message['power_lifetime'] = float(parts[4].split('L')[1])
        message['power_session'] = float(parts[15].split('E')[1]) if message['status'] == 'charging' else 0.0
        message['temperature'] = float(parts[6].split('T')[1])*1.8+32
        message['voltage'] = float(parts[3].split('V')[1])*0.1
    except:
        logging.exception('failed to process basic message')
        return None
    return message

def basic_message_publish(message):
    logging.debug('basic message {}'.format(message))
    pass

def remote_data_handler(data):
    logging.debug('remote: {}'.format(data))
    return data

def local_data_handler(data):
    logging.debug('local : {}'.format(data))
    message = basic_message_try_parse(data)
    if message:
        basic_message_publish(message)
    return data

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=AP_DESCRIPTION)

    parser.add_argument('-s', '--src', required=True, default="127.0.0.1:8047",
                        help="Source IP and port, (default: %(default)s)")
    parser.add_argument('-d', '--dst', required=True, 
                        help='Destination IP and port of EnelX Server.')
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("-u", "--user", type=str, help="MQTT username")
    parser.add_argument("-P", "--password", type=str, help="MQTT password")
    parser.add_argument("-H", "--host", type=str, default="127.0.0.1",
                        help="MQTT hostname to connect to (default: %(default)s)")
    parser.add_argument("-p", "--port", type=int, default=1883,
                        help="MQTT port (default: %(default)s)")
    parser.add_argument("-r", "--retain", action="store_true")
    parser.add_argument("-f", "--force_update", action="store_true",
                        help="Append 'force_update = true' to all configs.")
    parser.add_argument("-D", "--discovery-prefix", type=str,
                        dest="discovery_prefix",
                        default="homeassistant",
                        help="Home Assistant MQTT topic prefix (default: %(default)s)")
    parser.add_argument("-i", "--interval", type=int,
                        dest="discovery_interval",
                        default=600,
                        help="Interval to republish config topics in seconds (default: %(default)d)")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    pyproxy.LOCAL_DATA_HANDLER = local_data_handler
    pyproxy.REMOTE_DATA_HANDLER = remote_data_handler

    pyproxy.udp_proxy(args.src, args.dst)

if __name__ == '__main__':
    main()
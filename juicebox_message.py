#
# Original source  : https://github.com/philipkocanda/juicebox-protocol
#
from juicebox_checksum import JuiceboxChecksum
from juicebox_exceptions import JuiceboxInvalidMessageFormat
import datetime
import logging
import re

_LOGGER = logging.getLogger(__name__)

#
# try to detect message format and use correct class for decoding
#
def juicebox_message_from_string(string : str):
   if string[0:3] == "CMD":
      return JuiceboxCommand().from_string(string)

   msg = re.search(r'^(?P<id>[0-9]+):(?P<version>v[0-9]+[eu])', string)

   if msg:
      # check for encrypted message
      #   https://github.com/snicker/juicepassproxy/issues/73
      if msg.group('version') == 'v09e':
         # encrypted version
         raise JuiceboxInvalidMessageFormat(f"Unable to parse encrypted message: '{string}'")

      return JuiceboxMessage().from_string(string)

   raise JuiceboxInvalidMessageFormat(f"Unable to parse message: '{string}'")
      
      
      
class JuiceboxMessage:

    def __init__(self) -> None:
        self.payload_str = None
        self.checksum_str = None
        self.values = None

        pass


    def parse_values(self):
        # Nothing to do here now
        _LOGGER.debug(f"No values conversion on base JuiceboxMessage : {self.values}")
    
    def from_string(self, string: str) -> 'Message':
        _LOGGER.info(f"from_string {string}")
        msg = re.search(r'((?P<payload>.*)!(?P<checksum>[A-Z0-9]{3})(?:\$|:))', string)

        if msg is None:
            raise JuiceboxInvalidMessageFormat(f"Unable to parse message: '{string}'")

        self.payload_str = msg.group('payload')
        tmp = self.payload_str
        values = {}
        while len(tmp) > 0:
            # For version there is an ending 'u' 
            data = re.search(r'((?P<serial>[0-9]+):)?[,]?(?P<type>[A-Za-z]+)(?P<value>[-]?[0-9]+[u]?)', tmp)
            if data:
                if data.group("serial"):
                   values["serial"] = data.group("serial")
                values[data.group("type")] = data.group("value")
                tmp = tmp[len(data.group(0)):]
            else: 
               _LOGGER.error(f"unable to parse value from message {tmp}")
               break
        self.values = values
        self.parse_values()
        self.checksum_str = msg.group('checksum')
        return self


    def get_value(self, type):
        if type in self.values:
           return self.values[type]
        return None
        
    def checksum(self) -> JuiceboxChecksum:
        return JuiceboxChecksum(self.payload_str)


    def checksum_computed(self) -> str:
        return self.checksum().base35()


    def build_payload(self) -> None:
        if self.payload_str:
            return

        _LOGGER.error("this base class cannot built payload")


    def build(self) -> str:
        self.build_payload()
        return f"{(self.payload_str)}!{self.checksum_str}$"


    def inspect(self) -> dict:
        data = {
            "payload_str": self.payload_str,
            "checksum_str": self.checksum_str,
            "checksum_computed": self.checksum_computed(),
        }

        # Generic base classe does not know specific fields, then put all split values
        if self.values:
            data.update(self.values)

        return data


    def __str__(self):
        return self.build()

class JuiceboxCommand(JuiceboxMessage):

    def __init__(self, previous=None, new_version=False) -> None:
        super().__init__()
        self.new_version = new_version
        self.command = 6 # Alternates between C242, C244, C008, C006. Meaning unclear.

        # increments by one for every message until 999 then it loops back to 1
        if previous:
            self.counter = previous.counter + 1
            if (self.counter > 999):
               self.counter = 1
            self.offline_amperage = previous.offline_amperage
            self.instant_amperage = previous.instant_amperage 
        else:
            self.counter = 1
            self.offline_amperage = 0
            self.instant_amperage = 0

        self.time = datetime.datetime.today()

    def inspect(self) -> dict:
        data = {
            "command": self.command,
            "offline_amperage": self.offline_amperage,
            "instant_amperage": self.instant_amperage,
            "counter": self.counter,
            "payload_str": self.payload_str,
            "checksum_str": self.checksum_str,
            "checksum_computed": self.checksum_computed(),
        }

        # add any extra received value        
        if self.values:
            data.update(self.values)

        return data

    def build_payload(self) -> None:
        if self.payload_str:
            return

        weekday = self.time.strftime('%w') # 0 = Sunday, 6 = Saturday

        # Original comment :
        #     Instant amperage may need to be represented using 4 digits (e.g. 0040) on newer Juicebox versions.
        # mine wich send data using version 09u works with 4 digits on offline and 3 digit on instant
        #    sizes got from original packet dump when communicating with enel x server
        #
        # https://github.com/snicker/juicepassproxy/issues/39#issuecomment-2002312548
        #   @FalconFour definition of currents
        if self.new_version:
            self.payload_str = f"CMD{weekday}{self.time.strftime('%H%M')}A{self.instant_amperage:04d}M{self.offline_amperage:03d}C{self.command:03d}S{self.counter:03d}"
        else:
            self.payload_str = f"CMD{weekday}{self.time.strftime('%H%M')}A{self.instant_amperage:02d}M{self.offline_amperage:02d}C{self.command:03d}S{self.counter:03d}"
        self.checksum_str = self.checksum_computed()

    def parse_values(self):
        if "CMD" in self.values:
            self.values["DOW"] = self.values["CMD"][0]
            self.values["HHMM"] = self.values["CMD"][1:]
            self.values.pop("CMD")
        if "C" in self.values:
            self.command = int(self.values["C"])
            self.values.pop("C")
        if "A" in self.values:
            self.offline_amperage = int(self.values["A"])
            self.values.pop("A")
        if "M" in self.values:
            self.instant_amperage = int(self.values["M"])
            self.values.pop("M")
        if "S" in self.values:
            self.counter = int(self.values["S"])
            self.values.pop("S")
            
        _LOGGER.info(f"parse_values values {self.values}")

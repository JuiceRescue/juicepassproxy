#
# Original source  : https://github.com/philipkocanda/juicebox-protocol
#
from juicebox_checksum import JuiceboxChecksum
from juicebox_exceptions import JuiceboxInvalidMessageFormat
import datetime
import logging
import re

_LOGGER = logging.getLogger(__name__)

class JuiceboxMessage:

    def __init__(self) -> None:
        self.payload_str = None
        self.checksum_str = None
        self.values = None

        pass


    def from_string_values(self, values):
        # Nothing to do here now
        _LOGGER.info(f"No conversion on base JuiceboxMessage : {values}")
    
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
            data = re.search(r'[,:]?(?P<type>[A-Za-z]+)(?P<value>[-]?[0-9]+[u]?)', tmp)
            if data:
                values[data.group("type")] = data.group("value")
                tmp = tmp[len(data.group(0)):]
            else: 
               break
        self.from_string_values(values)
        self.values = values
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
        return {
            "payload_str": self.payload_str,
            "checksum_str": self.checksum_str,
            "checksum_computed": self.checksum_computed(),
        }


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
        return {
            "command": self.command,
            "offline_amperage": self.offline_amperage,
            "instant_amperage": self.instant_amperage,
            "counter": self.counter,
            "payload_str": self.payload_str,
            "checksum_str": self.checksum_str,
            "checksum_computed": self.checksum_computed(),
        }

    def build_payload(self) -> None:
        if self.payload_str:
            return

        weekday = self.time.strftime('%w') # 0 = Sunday, 6 = Saturday

        # Original comment :
        #     Instant amperage may need to be represented using 4 digits (e.g. 0040) on newer Juicebox versions.
        # mine wich send data using version 09u works with 4 digits on offline and 3 digit on instant
        if self.new_version:
            self.payload_str = f"CMD{weekday}{self.time.strftime('%H%M')}A{self.offline_amperage:04d}M{self.instant_amperage:03d}C{self.command:03d}S{self.counter:03d}"
        else:
            self.payload_str = f"CMD{weekday}{self.time.strftime('%H%M')}A{self.offline_amperage:02d}M{self.instant_amperage:02d}C{self.command:03d}S{self.counter:03d}"
        self.checksum_str = self.checksum_computed()

    def from_string_values(self, values):
        if "C" in values:
            self.command = int(values["C"])
        if "A" in values:
            self.offline_amperage = int(values["A"])
        if "M" in values:
            self.instant_amperage = int(values["M"])
        if "S" in values:
            self.counter = int(values["S"])
        _LOGGER.info(f"from_sring values {values}")

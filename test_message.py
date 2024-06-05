import unittest
from juicebox_message import juicebox_message_from_string,JuiceboxMessage, JuiceboxCommand
from juicebox_exceptions import JuiceboxInvalidMessageFormat
import datetime

class TestMessage(unittest.TestCase):
    def test_message_building(self):
        m = JuiceboxCommand()
        m.time = datetime.datetime(2012, 3, 23, 23, 24, 55, 173504)
        m.offline_amperage = 16
        m.instant_amperage = 20
        print(m.build())
        print(m.inspect())
        self.assertEqual(m.build(), "CMD52324A20M16C006S001!5RE$")


    def test_message_building_new(self):
        m = JuiceboxCommand(new_version=True)
        m.time = datetime.datetime(2012, 3, 23, 23, 24, 55, 173504)
        m.offline_amperage = 16
        m.instant_amperage = 20
        print(m.build())
        print(m.inspect())
        self.assertEqual(m.build(), "CMD52324A0020M016C006S001!YUK$")


    def test_message_validation(self):
        with self.assertRaises(JuiceboxInvalidMessageFormat):
            m = juicebox_message_from_string("g4rbl3d")


    def test_command_message_parsing(self):
        """
        Command messages are typically sent by the Cloud to the Juicebox
        """
        raw_msg = "CMD41325A0040M040C006S638!5N5$"
        m = juicebox_message_from_string(raw_msg)
        self.assertEqual(m.payload_str, "CMD41325A0040M040C006S638")
        self.assertEqual(m.checksum_str, "5N5")
        self.assertEqual(m.checksum_str, m.checksum_computed())
        self.assertEqual(m.build(), raw_msg)
        self.assertEqual(m.get_value("DOW"), "4")
        self.assertEqual(m.get_value("HHMM"), "1325")

    def test_status_message_parsing(self):
        """
        Status messages are sent by the Juicebox
        """
        raw_msg = "0910042001260513476122621631:v09u,s627,F10,u01254993,V2414,L00004555804,S01,T08,M0040,C0040,m0040,t29,i75,e00000,f5999,r61,b000,B0000000!55M:"

        m = juicebox_message_from_string(raw_msg)
        self.assertEqual(m.payload_str, "0910042001260513476122621631:v09u,s627,F10,u01254993,V2414,L00004555804,S01,T08,M0040,C0040,m0040,t29,i75,e00000,f5999,r61,b000,B0000000")
        self.assertEqual(m.checksum_str, "55M")
        self.assertEqual(m.checksum_str, m.checksum_computed())
        self.assertEqual(m.get_value("C"), "0040")
        self.assertEqual(m.get_value("v"), "09u")
        self.assertEqual(m.get_value("serial"), "0910042001260513476122621631")
        # self.assertEqual(m.build(), raw_msg)

    def test_message_checksums(self):
        messages = [
            'CMD41325A0040M040C006S638!5N5$', # @MrDrew514 (v09u)
            'CMD62210A20M18C006S006!31Y$',
            'CMD62228A20M15C008S048!IR4$',
            'CMD62207A20M20C244S997!R5Y$',
            'CMD62207A20M20C008S996!ZI4$',
            'CMD62201A20M20C244S981!ECD$',
            'CMD62201A20M20C006S982!QT8$',
            'CMD31353A0000M010C244S741!2B3$', # (v09u)
            # Original message changed to remove real serial number
            '0910000000000000000000000000:v09u,s001,F31,u00412974,V1366,L00004262804,S02,T28,M0024,C0024,m0032,t09,i23,e-0001,f5990,r99,b000,B0000000,P0,E0004501,A00161,p0996!ZW5:'
        ]

        for message in messages:
            m = juicebox_message_from_string(message)
            print(m.inspect())

            self.assertEqual(m.checksum_str, m.checksum_computed())

if __name__ == '__main__':
    unittest.main()

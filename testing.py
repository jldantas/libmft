import unittest
import datetime

#import libmft.api
#from libmft.flagsandtypes import AttrTypes, FileInfoFlags, MftUsageFlags

from libmft.attrcontent import Timestamps, StandardInformation#, StandardInformation2
from libmft.util.functions import convert_filetime
from libmft.exceptions import *

class TestDateTimeConversion(unittest.TestCase):
    def test_zero(self):
        base = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
        self.assertEqual(convert_filetime(0), base)
        pass

    def test_microseconds(self):
        base = datetime.datetime(1601, 1, 1, microsecond=10, tzinfo=datetime.timezone.utc)
        self.assertEqual(convert_filetime(100), base)
        pass

    def test_normal_number(self):
        base = datetime.datetime(4198, 6, 12, 10, 17, 3, 124368, tzinfo=datetime.timezone.utc)
        self.assertEqual(convert_filetime(819674578231243602), base)
    #a = "\x38\x98\x35\xBA\xDD\x42\xD3\x01"


class TestTimestamps(unittest.TestCase):
    zero = b"\x00\x00\x00\x00\x00\x00\x00\x00"
    full = b"\x38\x98\x35\xBA\xAD\x42\xD3\x01\x36\x98\x35\xBA\xDD\x42\xD3\x01\x38\x08\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\x7A\xDD\x42\xD3\x01"
    all_zero = Timestamps.create_from_binary(zero * 4)
    base = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
    t_full = Timestamps.create_from_binary(full)

    def test_created_zero(self):
        self.assertEqual(self.all_zero.created, self.base)

    def test_changed_zero(self):
        self.assertEqual(self.all_zero.changed, self.base)

    def test_mft_changed_zero(self):
        self.assertEqual(self.all_zero.mft_changed, self.base)

    def test_accessed_zero(self):
        self.assertEqual(self.all_zero.accessed, self.base)

    def test_wrong_size_binary_stream(self):
        with self.assertRaises(ContentError):
            Timestamps.create_from_binary(self.zero * 2)

    def test_created_full(self):
        a = datetime.datetime(2017, 10, 11, 16, 26, 44, 472632, tzinfo=datetime.timezone.utc)
        self.assertEqual(self.t_full.created, a)

    def test_changed_full(self):
        a = datetime.datetime(2017, 10, 11, 22, 10, 20, 315654, tzinfo=datetime.timezone.utc)
        self.assertEqual(self.t_full.changed, a)

    def test_mft_changed_full(self):
        a = datetime.datetime(2017, 10, 11, 22, 10, 20, 311968, tzinfo=datetime.timezone.utc)
        self.assertEqual(self.t_full.mft_changed, a)

    def test_accessed_full(self):
        a = datetime.datetime(2017, 10, 11, 22, 8, 32, 941472, tzinfo=datetime.timezone.utc)
        self.assertEqual(self.t_full.accessed, a)


def main():
    #created, changed, mft_changed, accessed
    #a = b"\x38\x98\x35\xBA\xDD\x42\xD3\x01 \x38\x98\x35\xBA\xDD\x42\xD3\x01 \x38\x98\x35\xBA\xDD\x42\xD3\x01 \x38\x98\x35\xBA\xDD\x42\xD3\x01"
    # a = b"\x38\x98\x35\xBA\xAD\x42\xD3\x01\x36\x98\x35\xBA\xDD\x42\xD3\x01\x38\x08\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\x7A\xDD\x42\xD3\x01"
    #
    # b = Timestamps.create_from_binary(a)
    # print(repr(b.accessed))

    #a = b"\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    a = b"\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b = b"\x00\x25\x72\xA3\x48\x08\xD2\x01\x00\x25\x72\xA3\x48\x08\xD2\x01\x29\x47\x8D\x1D\x99\x42\xD3\x01\x29\x47\x8D\x1D\x99\x42\xD3\x01\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xED\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xE0\xC4\x7D\x01\x00\x00\x00\x00"
    c = StandardInformation.create_from_binary(a)
    d = StandardInformation.create_from_binary(b)
    #c1 = StandardInformation2.create_from_binary(a)
    #d1 = StandardInformation2.create_from_binary(b)
    print(c)
    print()
    print(d)
    print("-"*80)
    #print(c1, "\n\n", d1)

    unittest.main()

    #TestDateTimeConversion()

if __name__ == '__main__':
    main()

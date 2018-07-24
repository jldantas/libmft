import unittest
import datetime

#import libmft.api
#from libmft.flagsandtypes import AttrTypes, FileInfoFlags, MftUsageFlags

from libmft.attrcontent import Timestamps, StandardInformation, FileName
from libmft.util.functions import convert_filetime
from libmft.exceptions import *

    #a = "\x38\x98\x35\xBA\xDD\x42\xD3\x01"

class TestMFT(unittest.TestCase):
    std_info_raw = b"\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

    def test_date_time_conversion(self):
        zero = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
        msec = datetime.datetime(1601, 1, 1, microsecond=10, tzinfo=datetime.timezone.utc)
        normal = datetime.datetime(4198, 6, 12, 10, 17, 3, 124368, tzinfo=datetime.timezone.utc)
        self.assertEqual(convert_filetime(0), zero)
        self.assertEqual(convert_filetime(100), msec)
        self.assertEqual(convert_filetime(819674578231243602), normal)

    def test_timestamp_creation(self):
        full = b"\x38\x98\x35\xBA\xAD\x42\xD3\x01\x36\x98\x35\xBA\xDD\x42\xD3\x01\x38\x08\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\x7A\xDD\x42\xD3\x01"
        t_full = Timestamps.create_from_binary(full)
        crtime = datetime.datetime(2017, 10, 11, 16, 26, 44, 472632, tzinfo=datetime.timezone.utc)
        mtime = datetime.datetime(2017, 10, 11, 22, 10, 20, 315654, tzinfo=datetime.timezone.utc)
        ctime = datetime.datetime(2017, 10, 11, 22, 10, 20, 311968, tzinfo=datetime.timezone.utc)
        atime = datetime.datetime(2017, 10, 11, 22, 8, 32, 941472, tzinfo=datetime.timezone.utc)
        self.assertEqual(t_full.created, crtime)
        self.assertEqual(t_full.changed, mtime)
        self.assertEqual(t_full.mft_changed, ctime)
        self.assertEqual(t_full.accessed, atime)

    def test_timestamp_comparison(self):
        full = b"\x38\x98\x35\xBA\xAD\x42\xD3\x01\x36\x98\x35\xBA\xDD\x42\xD3\x01\x38\x08\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\x7A\xDD\x42\xD3\x01"
        t_full = Timestamps.create_from_binary(full)
        t_full2 = Timestamps.create_from_binary(full)
        t_zero = Timestamps.create_from_binary(b"\x00" * Timestamps.get_representation_size())
        self.assertEqual(t_full, t_full2)
        self.assertNotEqual(t_full, t_zero)

    def test_timestamp_binary_error(self):
        with self.assertRaises(ContentError):
            Timestamps.create_from_binary(b"\x00" * 2)

    def test_standard_info_creation(self):
        a = b"\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x38\x98\x35\xBA\xDD\x42\xD3\x01\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        #std_info = StandardInformation(())

        #StandardInformation(timestamps=Timestamps(created=2017-10-11 22:10:20.315654+00:00, changed=2017-10-11 22:10:20.315654+00:00, mft_changed=2017-10-11 22:10:20.315654+00:00, accessed=2017-10-11 22:10:20.315654+00:00), flags=FileInfoFlags.SYSTEM|HIDDEN, max_n_versions=0, version_number=0, class_id=0, owner_id=0, security_id=256, quota_charged=0, usn=0)

        #StandardInformation(timestamps=Timestamps(created=2016-09-06 14:12:02+00:00, changed=2016-09-06 14:12:02+00:00, mft_changed=2017-10-11 13:59:11.710392+00:00, accessed=2017-10-11 13:59:11.710392+00:00), flags=FileInfoFlags.ARCHIVE, max_n_versions=0, version_number=0, class_id=0, owner_id=0, security_id=749, quota_charged=0, usn=25019616)



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

    a = b"\x87\x60\x02\x00\x00\x00\x02\x00\x29\x47\x8D\x1D\x99\x42\xD3\x01\x29\x47\x8D\x1D\x99\x42\xD3\x01\x29\x47\x8D\x1D\x99\x42\xD3\x01\x29\x47\x8D\x1D\x99\x42\xD3\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x20\x00\x00\x00\x00\x00\x00\x00\x0C\x02\x43\x00\x49\x00\x53\x00\x43\x00\x4F\x00\x45\x00\x7E\x00\x31\x00\x2E\x00\x43\x00\x48\x00\x4D\x00"
    print(FileName.create_from_binary(memoryview(a)))
    #print(c)
    print()
    #print(d)
    print("-"*80)
    #print(c1, "\n\n", d1)

    unittest.main()

    #TestDateTimeConversion()

if __name__ == '__main__':
    main()

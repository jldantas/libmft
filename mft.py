import struct
import collections
from datetime import datetime as _datetime, timedelta as _timedelta
import enum
import mftres.data

test = "./mft_samples/MFT_singlefile.bin"


def convert_filetime(filetime):
    return _datetime(1601, 1, 1) + _timedelta(microseconds=(filetime/10))

MFTHeader = collections.namedtuple("MFTHeader",
    ["signature", "fx_arr_pointer", "fx_count", "lsn", "seq_number",
    "hard_link_count", "offset_first_attr", "usage_flags", "mft_logical_size",
    "mft_phys_size", "parent_dir", "nex_attr_id", "padding_xp", "mft_record"])
MFT_HEADER_REPR = struct.Struct("4s2hQ4h2IQ2hI")
#TODO cofirm header size, some sources says 42 bytes. Mine has 48?

ATTR_HEADER_REPR = struct.Struct("2I2B3H")
AttributeHeader = collections.namedtuple("AttributeHeader",
    ["attr_type_id", "len_attr", "nonresident_flag", "name_len",
    "name_offset", "flags", "attr_id"])

class AttrTypes(enum.Enum):
    STANDARD_INFORMATION = 0x10
    ATTRIBUTE_LIST = 0x20
    FILE_NAME = 0x30
    OBJECT_ID = 0X40
    SECURITY_DESCRIPTOR = 0x50
    VOLUME_NAME = 0x60
    VOLUME_INFORMATION = 0x70
    DATA = 0x80
    INDEX_ROOT = 0x90
    INDEX_ALLOCATION = 0xA0
    BITMAP = 0xB0
    REPARSE_POINT = 0xC0
    LOGGED_TOOL_STREAM = 0x100

#TODO resident, named attribute?  https://flatcap.org/linux-ntfs/ntfs/concepts/attribute_header.html

RESIDENT_ATTR_HEADER_REPR = struct.Struct("IHBx")
ResidentAttrHeader = collections.namedtuple("ResidentAttrHeader",
    ["content_len", "content_offset", "indexed_flag"])

class StdInfoFlags(enum.IntFlag):
    READ_ONLY = 0x0001
    HIDDEN = 0x0002
    SYSTEM = 0x0004
    ARCHIVE = 0x0020
    DEVICE = 0x0040
    NORMAL = 0x0080
    TEMPORARY = 0x0100
    SPARSE_FILE = 0x0200
    REPARSE_POINT = 0x0400
    COMPRESSED = 0x0800
    OFFLINE = 0x1000
    CONTENT_NOT_INDEXED = 0x2000
    ENCRYPTED = 0x4000


# STD_TIME_REPR = struct.Struct("4Q6I2Q")
# StandardInformation = collections.namedtuple("StandardInformation",
#     ["creation_time", "file_altered_time", "mft_altered_time", "accessed_time",
#     "flags", "max_n_ver", "ver_n", "class_id", "owner_id", "sec_id",
#     "quota_charged", "usn"])
class StandardInformation():
    #TODO code to deal with NTFS version less than 3?
    _STD_TIME_REPR = struct.Struct("4Q6I2Q")

    def __init__(self, attr_view):
        temp = self._STD_TIME_REPR.unpack(attr_view)

        self.timestamps = {}
        self.timestamps["created"] = convert_filetime(temp[0])
        self.timestamps["changed"] = convert_filetime(temp[1])
        self.timestamps["mft_change"] = convert_filetime(temp[2])
        self.timestamps["accessed"] = convert_filetime(temp[3])
        self.flags = StdInfoFlags(temp[4])
        self.max_n_ver = temp[5]
        self.ver_n = temp[6]
        self.class_id = temp[7]
        self.owner_id = temp[8]
        self.security_id = temp[9]
        self.quota_charged = temp[10]
        self.usn = temp[11]

    def __len__(self):
        return self._STD_TIME_REPR.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(timestamps={}, flags={!s}, max_n_ver={}, ver_n={}, class_id={}, owner_id={}, security_id={}, quota_charged={}, usn={})'.format(
            self.timestamps, self.flags, self.max_n_ver, self.ver_n, self.class_id,
            self.owner_id, self.security_id, self.quota_charged, self.usn)

class NameType(enum.Enum):
    POSIX = 0x0 #unicode, case sensitive
    WIN32 = 0x1 #unicode, case insensitive
    DOS = 0x2 #8.3 ASCII, case insensitive
    WIN32_DOS = 0X3 #Win32 fits dos space

class FileName():
    #name is missing, as encoding changes. It is added in the
    #initialization of the instance
    _FILENAME_REPR = struct.Struct("7QI2H")

    def __init__(self, attr_view):
        print(len(attr_view.tobytes()))
        temp = self._FILENAME_REPR.unpack(attr_view[:self._FILENAME_REPR.size])

        self.timestamps = {}
        self.parent_dir = temp[0]
        self.timestamps["created"] = convert_filetime(temp[1])
        self.timestamps["changed"] = convert_filetime(temp[2])
        self.timestamps["mft_change"] = convert_filetime(temp[3])
        self.timestamps["accessed"] = convert_filetime(temp[4])
        self.allocated_file_size = temp[5]
        self.file_size = temp[6]
        self.flags = StdInfoFlags(temp[7])
        self.name_len = temp[8]
        self.name_type = NameType(temp[9])

        size = self._FILENAME_REPR.size
        print("size", size, "name_len", self.name_len)
        #TODO correct conversion of the string shit
        self.name = attr_view[size:size+self.name_len].tobytes()

    def __len__(self):
        #TODO define if len is going to be the raw or if it is going to be
        #with the name converted
        pass
        #return self._STD_TIME_REPR.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(parent_dir={}, timestamps={}, allocated_file_size={}, file_size={}, flags={!s}, name_len={}, name_type={!s}, name={}'.format(
            self.parent_dir, self.timestamps, self.allocated_file_size,
            self.file_size, self.flags, self.name_len, self.name_type,
            self.name)

def apply_fixup_array(bin_view, fx_offset, fx_count, mft_phys_size):
    '''This function reads the fixup array and apply the correct values
    to the underlying binary stream. This function changes the entries
    in memory.
    '''
    #TODO evaluate the passing of the mft_header instead of the attributes
    fx_array = bin_view[fx_offset:fx_offset+(2 * fx_count)]
    #the array is composed of the signature + substitutions, so fix that
    fx_len = fx_count - 1
    #we can infer the sector size based on the size of the mft
    sector_size = int(mft_phys_size / fx_len)
    index = 1
    position = (sector_size * index) - 2
    while (position <= mft_phys_size):
        if bin_view[position:position+1].tobytes() == fx_array[:1].tobytes():
            #the replaced part must always match the signature!
            bin_view[position:position+1] = fx_array[index * 2:(index * 2) + 1]
        else:
            print("REPLACING WRONG PLACE, STOP MOTHERFUCKER!")
            #TODO error handling
        index += 1
        position = (sector_size * index) - 2

def read_mft_attribute(bin_view, attr_offset):
    '''Reads the attribute at 'attr_offset' of the memoryview. This function
    reads the attribute, correctly check if it is resident or not and
    fires the reading of the attribute specific information
    '''
    print("ATTR_OFFSET:", hex(attr_offset))
    attr_header = AttributeHeader._make(ATTR_HEADER_REPR.unpack(bin_view[attr_offset:attr_offset+ATTR_HEADER_REPR.size]))
    print(attr_offset, attr_header)
    if not attr_header.nonresident_flag:
        resident_attr_header = ResidentAttrHeader._make(RESIDENT_ATTR_HEADER_REPR.unpack(bin_view[attr_offset+ATTR_HEADER_REPR.size:attr_offset+ATTR_HEADER_REPR.size + RESIDENT_ATTR_HEADER_REPR.size]))
        print(resident_attr_header)
        attr_view = bin_view[attr_offset+resident_attr_header.content_offset:attr_offset+resident_attr_header.content_offset+resident_attr_header.content_len]
        if attr_header.attr_type_id == AttrTypes.STANDARD_INFORMATION.value:
            std_info = StandardInformation(attr_view)
            print(std_info)
        elif attr_header.attr_type_id == AttrTypes.FILE_NAME.value:
            file_name = FileName(attr_view)
            print(file_name)
        else:
            print("WE DON'T KNOW HOW TO TREAT THIS ATTRIBUTE YET")
    else:
        print("NON RESIDENT NOT READY YET")

    return attr_header

def read_mft_entry(bin_stream):
    '''Expects a writeable array with support to memoryview. Normally
    this would be a bytearray type. Once it has that, it reads the MFT
    and the necessary attributes. This read exactly one entry.
    '''
    #TODO have a "attribute parser" and a dispatcher?
    bin_view = memoryview(bin_stream)
    mft_header = MFTHeader._make(MFT_HEADER_REPR.unpack(bin_view[:MFT_HEADER_REPR.size]))
    #TODO Test if the fixup offset is smaller than the header size. It must always
    #be true. Otherwise we have a very serious problem with the header interpretation

    #use the fixup array to fix the memory, so we don't have to worry about this anymore
    apply_fixup_array(bin_view, mft_header.fx_arr_pointer,
            mft_header.fx_count, mft_header.mft_phys_size)

    attr_offset = mft_header.offset_first_attr
    i = 0
    while (bin_view[attr_offset:attr_offset+4] != b'0xffffffff'):
        attr_offset += read_mft_attribute(bin_view, attr_offset).len_attr
        if i > 2:
            break
        else:
            i += 1


    #print(bin_view)
    print(mft_header)
    #print(bytes(bin_view))
    #print(MFTHeader._source)

    bin_view.release() #release the underlying buffer

def find_mft_size(file_object):
    sizes = [1024, 4096, 512, 2048]
    sigs = [b"FILE", b"BAAD", b"INDX"]

    first_sig = file_object.read(4)
    second_sig = None
    if first_sig not in sigs:
        #TODO error handling
        print("SIGNATURE NOT FOUND")
    for size in sizes:
        file_object.seek(size, 0)
        second_sig = file_object.read(4)
        if second_sig in sigs:
            #TODO add logging
            break
    file_object.seek(0)

    return size

def main():
    sizes = [1024, 4096, 512, 2048]
    sigs = [b"FILE", b"BAAD", b"INDX"]

    with open(test, "rb") as mft_file:
        mftres.data.MFT(mft_file)

        # mft_size = find_mft_size(mft_file)
        # data_buffer = bytearray(mft_size)
        # while mft_file:
        #     mft_file.readinto(data_buffer)
        #     mft_entry =mftres.data.MFTEntry(data_buffer)
        #     break




#TODO read the first entry to figure what is the size of the mft entry, for
#testing, let's default to 1024
'''data_buffer = bytearray(1024)
with open(test, "rb") as mft_file:
    mft_file.readinto(data_buffer)
    read_mft_entry(data_buffer)
'''

'''
with open(test, "rb") as mft_file:
    temp = mft_file.read(mft_header.size)
    mft_header_raw = mft_header.unpack(temp)
    header_conv = MFTHeader._make(mft_header_raw)
    print(header_conv._source)
    print("mft header size:", mft_header.size)
    print("yo", mft_header_raw)
    print("{},{:#x},{:#x},{:#x},{:#x},{:#x},{:#x},{:#x},{:#x},{:#x},{:#x},{:#x},{:#x},{:#x}".format(*mft_header_raw))
    print(header_conv)

    mft_file.seek(header_conv.offset_first_attr, 0)
    temp = mft_file.read(attribute_header.size)
    attribute_conv = AttributeHeader._make(attribute_header.unpack(temp))
    print("attribute header size:", attribute_header.size)
    print("yo2", attribute_header.unpack(temp))
    print(attribute_conv)
    print
'''

main()

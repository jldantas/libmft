import enum
import struct

from util.functions import convert_filetime

class AttrTypes(enum.Enum):
    '''Define MFT attributes types.'''
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

#******************************************************************************
# STANDARD_INFORMATION ATTRIBUTE
#******************************************************************************
class StdInfoFlags(enum.IntFlag):
    '''Define the possible flags for the STANDARD_INFORMATION attribute'''
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

class StandardInformation():
    '''Represents the STANDARD_INFORMATION converting the timestamps to
    datetimes and the flags to StdInfoFlags representation.
    '''
    _REPR = struct.Struct("4Q6I2Q")
    _REPR_NTFS_LE_3 = struct.Struct("4Q4I")

    def __init__(self, attr_view):
        try:
            temp = self._REPR.unpack(attr_view)
            self.ntfs3_plus = True
        except struct.error:
            temp = self._REPR_NTFS_LE_3.unpack(attr_view)
            self.ntfs3_plus = False

        self.timestamps = {}
        self.timestamps["created"] = convert_filetime(temp[0])
        self.timestamps["changed"] = convert_filetime(temp[1])
        self.timestamps["mft_change"] = convert_filetime(temp[2])
        self.timestamps["accessed"] = convert_filetime(temp[3])
        self.flags = StdInfoFlags(temp[4])
        self.max_n_ver = temp[5]
        self.ver_n = temp[6]
        self.class_id = temp[7]
        if (self.ntfs3_plus):
            self.owner_id = temp[8]
            self.security_id = temp[9]
            self.quota_charged = temp[10]
            self.usn = temp[11]

    @classmethod
    def size(cls, version3=True):
        if version3:
            return cls._REPR.size
        else:
            return cls._REPR_NTFS_LE_3.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        if self.ntfs3_plus:
            return self.__class__.__name__ + '(timestamps={}, flags={!s}, max_n_ver={}, ver_n={}, class_id={}, owner_id={}, security_id={}, quota_charged={}, usn={})'.format(
                self.timestamps, self.flags, self.max_n_ver, self.ver_n, self.class_id,
                self.owner_id, self.security_id, self.quota_charged, self.usn)
        else:
            return self.__class__.__name__ + '(timestamps={}, flags={!s}, max_n_ver={}, ver_n={}, class_id={})'.format(
                self.timestamps, self.flags, self.max_n_ver, self.ver_n, self.class_id)

#******************************************************************************
# FILENAME ATTRIBUTE
#******************************************************************************
class NameType(enum.Enum):
    '''Flags that define how the file name is encoded in the FILE_NAME attribute'''
    POSIX = 0x0 #unicode, case sensitive
    WIN32 = 0x1 #unicode, case insensitive
    DOS = 0x2 #8.3 ASCII, case insensitive
    WIN32_DOS = 0X3 #Win32 fits dos space

class FileName():
    '''Represents the FILE_NAME converting the timestamps to
    datetimes and the flags to StdInfoFlags representation.
    '''
    #name is missing, as encoding changes. It is added in the
    #initialization of the instance
    _REPR = struct.Struct("7Q2I2B")

    def __init__(self, attr_view):
        temp = self._REPR.unpack(attr_view[:self._REPR.size])

        self.timestamps = {}
        #TODO REALLY DEBUG/TEST THIS ARITHIMETIC!!!!!!
        self.parent_ref = (temp[0] & 0xffff000000000000) >> 48
        self.parent_seq = temp[0] & 0x0000ffffffffffff
        self.timestamps["created"] = convert_filetime(temp[1])
        self.timestamps["changed"] = convert_filetime(temp[2])
        self.timestamps["mft_change"] = convert_filetime(temp[3])
        self.timestamps["accessed"] = convert_filetime(temp[4])
        self.allocated_file_size = temp[5]
        self.file_size = temp[6]
        self.flags = StdInfoFlags(temp[7])
        self.reparse_value = temp[8]
        self.name_len = temp[9]
        self.name_type = NameType(temp[10])

        #TODO correct conversion of the string shit
        self.name = attr_view[self._REPR.size:].tobytes().decode("utf_16_le")
        if len(self.name) != self.name_len:
            #TODO error handling
            print("name size dont match. PROBLEM!")

    @classmethod
    def size(cls):
        return cls._REPR.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(parent_ref={}, parent_seq={}, timestamps={}, allocated_file_size={}, file_size={}, flags={!s}, name_len={}, name_type={!s}, name={}'.format(
            self.parent_ref, self.parent_seq, self.timestamps, self.allocated_file_size,
            self.file_size, self.flags, self.name_len, self.name_type,
            self.name)

#******************************************************************************
# DATA ATTRIBUTE
#******************************************************************************
class Data():
    '''This is a placeholder class to the data attribute. By itself, it does
    very little and holds almost no information. However, it holds the file size
    parsed from the DATA attribute and, if the data is resident, holds the
    content as well.
    '''
    def __init__(self, size, content=None):
        '''Initialize the class. It is recommended that the class methods
        "create_from_resident" or "create_from_nonresident" are used instead
        of calling the creation directly. Expects the size of the data attribute,
        in bytes, and the content, in case of a resident attribute
        '''
        self.size = size
        self.content = content

    @classmethod
    def create_from_resident(cls, bin_view):
        '''In case of a resident attribute, receives a binary_view of the content
        with this information we derive the size.
        '''
        return cls(len(bin_view), bin_view.tobytes())

    @classmethod
    def create_from_nonresident(cls):
        #TODO this part
        pass

    def __len__(self):
        return self.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(size={}, content={}'.format(
            self.size, self.content)

#******************************************************************************
# INDEX_ROOT ATTRIBUTE
#******************************************************************************
class IndexRoot():
    '''Represents the INDEX_ROOT
    '''
    #name is missing, as encoding changes. It is added in the
    #initialization of the instance
    _REPR = struct.Struct("3IB3x")

    def __init__(self, attr_view):
        temp = self._REPR.unpack(attr_view[:self._REPR.size])

        if temp[0]:
            self.attr_type = AttrTypes(temp[0])
        else:
            self.attr_type = None #TODO changing type in the middle is not good. review.
        self.collation_rule = temp[1] #TODO identify this?
        self.index_len_in_bytes = temp[2]
        self.index_len_in_cluster = temp[3]

    @classmethod
    def size(cls):
        return cls._REPR.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(attr_type={!s}, collation_rule={}, index_len_in_bytes={}, index_len_in_cluster={}'.format(
            self.attr_type, self.collation_rule, self.index_len_in_bytes,
            self.index_len_in_cluster)

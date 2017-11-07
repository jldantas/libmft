import enum
import struct
import collections
import logging

from libmft.attributes import AttrTypes
from libmft.util.functions import get_file_reference
from libmft.exceptions import MFTHeaderException, AttrHeaderException

MOD_LOGGER = logging.getLogger(__name__)

class MftSignature(enum.Enum):
    '''This Enum identifies the possible types of MFT entries. Mainly used by
    the MFTHeader, signature
    '''
    FILE = b"FILE"
    BAAD = b"BAAD"
    INDX = b"INDX"

class MftUsageFlags(enum.Enum):
    '''This Enum identifies the possible uses of a MFT entry. If it is not
    used, a file or a directory. Mainly used be the MFTHeader, usage_flags
    '''
    NOT_USED = 0x0000
    IN_USE = 0x0001
    DIRECTORY = 0x0002
    DIRECTORY_IN_USE = 0x0003
    UNKNOW = 0xFFFF

class AttrFlags(enum.Enum):
    '''Represents the possible flags for the AttributeHeader class.'''
    NORMAL = 0x0000
    COMPRESSED = 0x0001
    ENCRYPTED = 0x4000
    SPARSE = 0x8000

#TODO evaluate if converting a bunch of stuff to ctypes is a good idea

class MFTHeader():
    '''Represent the MFT header present in all MFT entries.'''
    #TODO create a way of dealing with XP only artefacts
    _REPR = struct.Struct("<4s2HQ4H2IQH2xI")
    ''' Signature - 4 = FILE or BAAD or INDX
        Fix Up Array offset - 2
        Fix Up Count - 2
        Log file sequence # (LSN) - 8
        Sequence number - 2
        Hard Link count - 2
        Offset to the first attribute - 2
        Usage flags - 2 (MftUsageFlags)
        MFT record logical size - 4 (in bytes)
        MFT record physical size - 4 (in bytes)
        Parent directory record # - 8
        Next attribute ID - 2 (xp only?)
        Padding  - 2 (xp only?)
        MFT record # - 4 (xp only?)
    '''

    def __init__(self, header_view):
        '''Creates an object of MFTHeader. Expects the bytes ("header_view")
        that compose the entry, with the correct size'''
        temp = self._REPR.unpack(header_view)

        try:
            self.signature = MftSignature(temp[0])
        except ValueError as e:
            MOD_LOGGER.exception("Entry has no valid signature.")
            raise
        self.fx_offset = temp[1]
        #Fixup array elements are always 16 bits and the first is the signature
        self.fx_count = temp[2]
        self.lsn = temp[3]
        self.seq_number = temp[4]
        self.hard_link_count = temp[5]
        self.first_attr_offset = temp[6]
        try:
            self.usage_flags = MftUsageFlags(temp[7])
        except ValueError:
            MOD_LOGGER.warning(f"Unkown MFT header usage flag {temp[7]} at entry {temp[12]}. Defaulting to UNKNOW.")
            self.usage_flags = MftUsageFlags.UNKNOW
        self.entry_len = temp[8] #in bytes
        self.entry_alloc_len = temp[9] #in bytes
        self.base_record_ref, self.base_record_seq = get_file_reference(temp[10])
        self.next_attr_id = temp[11]
        self.mft_record = temp[12]

        if self.fx_offset < MFTHeader.get_header_size():
            raise MFTHeaderException("Fix up array begins within the header.", self.mft_record)
        if self.entry_len > self.entry_alloc_len:
            raise MFTHeaderException("Logical size of the MFT is bigger than MFT allocated size.", self.mft_record)

    @classmethod
    def get_header_size(cls):
        '''Return the header size'''
        return cls._REPR.size

    def __len__(self):
        '''Returns the logical size of the mft entry'''
        self.entry_len

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(signature={!s}, fx_offset={:#06x}, fx_count={}, lsn={}, seq_number={}, hard_link_count={}, first_attr_offset={}, usage_flags={!s}, entry_len={}, entry_alloc_len={}, base_record_ref={:#x}, base_record_seq={:#x}, next_attr_id={}, mft_record={})'.format(
            self.signature, self.fx_offset, self.fx_count, self.lsn, self.seq_number,
            self.hard_link_count, self.first_attr_offset, self.usage_flags, self.entry_len,
            self.entry_alloc_len, self.base_record_ref, self.base_record_seq, self.next_attr_id,
            self.mft_record)

ResidentAttrHeader = collections.namedtuple("ResidentAttrHeader",
    ["content_len", "content_offset", "indexed_flag"])

NonResidentAttrHeader = collections.namedtuple("NonResidentAttrHeader",
    ["start_vcn", "end_vcn", "rl_offset", "compress_usize",
    "alloc_sstream", "curr_sstream", "init_sstream"])

class AttributeHeader():
    '''Represents the Attribute Header present in all attributes. Also accounts
    if the attribute is resident or non resident, which changes the size
    of the header itself'''
    _REPR = struct.Struct("<2I2B3H")
    ''' Attribute type id - 4 (AttrTypes)
        Length of the attribute - 4 (in bytes)
        Non-resident flag - 1 (0 - resident, 1 - non-resident)
        Length of the name - 1 (in number of characters)
        Offset to name - 2
        Flags - 2 (AttrFlags)
        Attribute id - 2
    '''
    _REPR_RESIDENT = struct.Struct("<IHBx")
    ''' Content length - 4
        Content offset - 2
        Indexed flag - 1
        Padding - 1
    '''
    #TODO dataruns
    _REPR_NONRESIDENT = struct.Struct("<2Q2H4x3Q")
    ''' Start virtual cluster number - 8
        End virtual cluster number - 8
        Runlist offset - 2
        Compression unit size - 2
        Padding - 4
        Allocated size of the stream - 8
        Current size of the stream - 8
        Initialized size of the stream - 8
    '''
    _ALWAYS_RESIDENT = [AttrTypes.STANDARD_INFORMATION, AttrTypes.FILE_NAME,
        AttrTypes.INDEX_ROOT]

    def __init__(self, header_view):
        '''Creates a header entry with from a memoryview. The memory view must
        start when the first attribute starts and must have all necssary data
        related to resident or non resident headers'''
        temp = self._REPR.unpack(header_view[:self._REPR.size])

        self.attr_type_id = AttrTypes(temp[0])
        self.attr_len = temp[1]
        self.is_non_resident = bool(temp[2])
        self.name_len = temp[3]
        self.name_offset = temp[4]
        self.flags = AttrFlags(temp[5])
        self.attr_id = temp[6]
        self.resident_header = None
        self.non_resident_header = None
        self.attr_name = None

        if self.name_len:
            self.attr_name = header_view[self.name_offset:self.name_offset+(2*self.name_len)].tobytes().decode("utf_16_le")

        if self.attr_type_id in AttributeHeader._ALWAYS_RESIDENT and self.is_non_resident:
            MOD_LOGGER.error(f"Attribute {self.attr_type.name} must always be resident")
            raise AttrHeaderException(f"Attribute {self.attr_type.name} is always resident.")

        if not self.is_non_resident:
            self.resident_header = ResidentAttrHeader._make(self._REPR_RESIDENT.unpack(header_view[self._REPR.size:self._REPR.size + self._REPR_RESIDENT.size]))
        else:
            self.non_resident_header = NonResidentAttrHeader._make(self._REPR_NONRESIDENT.unpack(header_view[self._REPR.size:self._REPR.size+self._REPR_NONRESIDENT.size]))

    @classmethod
    def get_base_header_size(cls):
        '''Return the header size WITHOUT accounting for a possible named attribute.'''
        return cls._REPR.size

    @classmethod
    def get_resident_header_size(cls):
        '''Return the resident attribute header size.'''
        return cls._REPR_RESIDENT.size

    @classmethod
    def get_non_resident_header_size(cls):
        '''Return the non resident attribute header size WITHOUT account for the
        datarun size or information.'''
        return cls._REPR_NONRESIDENT.size

    def __len__(self):
        '''Returns the logical size of the attribute'''
        return self.attr_len

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(attr_type_id={!s}, attr_len={}, nonresident_flag={}, name_len={}, name_offset={:#06x}, flags={!s}, attr_id={}, resident_header={}, non_resident_header={}, attr_name={})'.format(
            self.attr_type_id, self.attr_len, self.is_non_resident,
            self.name_len, self.name_offset, self.flags, self.attr_id,
            self.resident_header, self.non_resident_header, self.attr_name)

import enum
import struct
import collections

from mftres.attributes import AttrTypes
from util.functions import get_file_reference

class MftSignature(enum.Enum):
    FILE = b"FILE"
    BAAD = b"BAAD"
    INDX = b"INDX"

class MftUsageFlags(enum.Enum):
    NOT_USED = 0x0000
    IN_USE = 0x0001
    DIRECTORY = 0x0002
    DIRECTORY_IN_USE = 0x0003
    UNKNOW = 0xFFFF

class AttrFlags(enum.Enum):
    NORMAL = 0x0000
    COMPRESSED = 0x0001
    ENCRYPTED = 0x4000
    SPARSE = 0x8000

class MFTHeader():
    '''Represent the MFT header present in all MFT entries.'''
    #TODO create a way of dealing with XP only artefacts
    _REPR = struct.Struct("4s2HQ4H2IQH2xI")
    ''' Signature - 4 = FILE or BAAD or INDX
        Fix Up Array offset - 2
        Fix Up Count - 2
        Log file sequence # (LSN) - 8
        Sequence number - 2
        Hard Link count - 2
        Offset to the first attribute - 2
        Usage flags - 2 (MftUsageFlags)
        MFT record logical size - 4
        MFT record physical size - 4
        Parent directory record # - 8
        Next attribute ID - 2 (xp only?)
        Padding  - 2 (xp only?)
        MFT record # - 4 (xp only?)
    '''

    def __init__(self, header_view):
        '''Creates an object of MFTHeader. Expects the bytes ("header_view")
        that compose the entry, with the correct size'''
        temp = self._REPR.unpack(header_view)

        self.signature = MftSignature(temp[0])
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
            #TODO logging
            self.usage_flags = MftUsageFlags.UNKNOW
        self.mft_size = temp[8]
        self.mft_alloc_size = temp[9]
        self.base_record_ref, self.base_record_seq = get_file_reference(temp[10])
        self.next_attr_id = temp[11]
        self.mft_record = temp[12]

        if self.fx_offset < self.size():
            #TODO error handling
            print("FIX UP ARRAY BEGINS WITHIN THE HEADER! HUGE, HUGE, PROBLEM!")

    @classmethod
    def size(cls):
        '''Return the header size'''
        return cls._REPR.size

    def __len__(self):
        '''Returns the logical size of the mft entry'''
        self.mft_size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(signature={!s}, fx_offset={:#06x}, fx_count={}, lsn={}, seq_number={}, hard_link_count={}, first_attr_offset={}, usage_flags={!s}, mft_size={}, mft_alloc_size={}, base_record_ref={:#x}, base_record_seq={:#x}, next_attr_id={}, mft_record={})'.format(
            self.signature, self.fx_offset, self.fx_count, self.lsn, self.seq_number,
            self.hard_link_count, self.first_attr_offset, self.usage_flags, self.mft_size,
            self.mft_alloc_size, self.base_record_ref, self.base_record_seq, self.next_attr_id,
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
    #TODO create a way of dealing with XP only artefacts
    _REPR = struct.Struct("2I2B3H")
    ''' Attribute type id - 4 (AttrTypes)
        Length of the attribute - 4
        Non-resident flag - 1 (0 - resident, 1 - non-resident)
        Length of the name - 1 (in character)
        Offset to name - 2
        Flags - 2 (AttrFlags)
        Attribute id - 2
    '''
    _REPR_RESIDENT = struct.Struct("IHBx")
    ''' Content length - 4
        Content offset - 2
        Indexed flag - 1
        Padding - 1
    '''
    _REPR_NONRESIDENT = struct.Struct("2Q2H4x3Q")
    ''' Start virtual cluster number - 8
        End virtual cluster number - 8
        Runlist offset - 2
        Compression unit size - 2
        Padding - 4
        Allocated size of the stream - 8
        Current size of the stream - 8
        Initialized size of the stream - 8
    '''

    def __init__(self, header_view):
        temp = self._REPR.unpack(header_view[:self._REPR.size])

        self.attr_type_id = AttrTypes(temp[0])
        self.len_attr = temp[1]
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
        if not self.is_non_resident:
            self.resident_header = ResidentAttrHeader._make(self._REPR_RESIDENT.unpack(header_view[self._REPR.size:self._REPR.size + self._REPR_RESIDENT.size]))
        else:
            self.non_resident_header = NonResidentAttrHeader._make(self._REPR_NONRESIDENT.unpack(header_view[self._REPR.size:self._REPR.size+self._REPR_NONRESIDENT.size]))

    @classmethod
    def size(cls):
        #TODO account for self.attr_name
        '''Return the header size'''
        #TODO redo this. This is wrong by definition
        return cls._REPR.size

    def __len__(self):
        '''Returns the logical size of the attribute'''
        return self.len_attr

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(attr_type_id={!s}, len_attr={}, nonresident_flag={}, name_len={}, name_offset={:#06x}, flags={!s}, attr_id={}, resident_header={}, non_resident_header={}, attr_name={})'.format(
            self.attr_type_id, self.len_attr, self.is_non_resident,
            self.name_len, self.name_offset, self.flags, self.attr_id,
            self.resident_header, self.non_resident_header, self.attr_name)

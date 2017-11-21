'''
This module contains the definitions for all the headers when interpreting the
MFT.
'''
import enum
import struct
import collections
import logging

from libmft.flagsandtypes import AttrTypes, MftSignature, AttrFlags, MftUsageFlags
from libmft.util.functions import get_file_reference
from libmft.exceptions import HeaderError, AttrHeaderException

MOD_LOGGER = logging.getLogger(__name__)

#TODO evaluate if converting a bunch of stuff to ctypes is a good idea

class MFTHeader():
    '''Represent the MFT header present in all MFT entries.'''
    #TODO create a way of dealing with XP only artefacts
    _REPR = struct.Struct("<4s2HQ4H2IQH2xI")
    ''' Signature - 4 = FILE or BAAD
        Fix Up Array offset - 2
        Fix Up Count - 2
        Log file sequence # (LSN) - 8
        Sequence number - 2
        Hard Link count - 2
        Offset to the first attribute - 2
        Usage flags - 2 (MftUsageFlags)
        MFT record logical size - 4 (in bytes)
        MFT record physical size - 4 (in bytes)
        Base record # - 8
        Next attribute ID - 2 (xp only?)
        Padding  - 2 (xp only?)
        MFT record # - 4 (xp only?)
    '''
    def __init__(self, header=(None,)*14):
        '''Creates a MFTHeader object. The content has to be an iterable
        with precisely 14 elements in order.
        If content is not provided, a tuple filled with 'None' is the default
        argument.

        Args:
            content (iterable), where:
                [0] (bool) - does the entry has 'baad' signature?
                [1] (int) - offset to fixup array
                [2] (int) - number of elements in the fixup array
                [3] (int) - Log file sequence # (LSN)
                [4] (int) - sequence number
                [5] (int) - hard link count
                [6] (int) - offset to the first attribute
                [7] (MftUsageFlags) - usage flags
                [8] (int) - entry length (in bytes)
                [9] (int) - allocated size of the entry (in bytes)
                [10] (int) - base record reference
                [11] (int) - base record sequence
                [12] (int) - next attribute id
                [13] (int) - mft record number
        '''
        self._baad, self.fx_offset, self.fx_count, self.lsn, self.seq_number, \
        self.hard_link_count, self.first_attr_offset, self.usage_flags, \
        self._entry_len, self.entry_alloc_len, \
        self.base_record_ref, self.base_record_seq, self.next_attr_id, \
        self.mft_record = header

        #self._is_baad = True/False (depends on the signature)

    # def __init__(self, header_view):
    #     '''Creates an object of MFTHeader. Expects the bytes ("header_view")
    #     that compose the entry, with the correct size'''
    #     temp = self._REPR.unpack(header_view)
    #
    #     try:
    #         self.signature = MftSignature(temp[0])
    #     except ValueError as e:
    #         MOD_LOGGER.exception("Entry has no valid signature.")
    #         raise
    #     self.fx_offset = temp[1]
    #     #Fixup array elements are always 16 bits and the first is the signature
    #     self.fx_count = temp[2]
    #     self.lsn = temp[3]
    #     self.seq_number = temp[4]
    #     self.hard_link_count = temp[5]
    #     self.first_attr_offset = temp[6]
    #     try:
    #         self.usage_flags = MftUsageFlags(temp[7])
    #     except ValueError:
    #         MOD_LOGGER.warning(f"Unkown MFT header usage flag {temp[7]} at entry {temp[12]}. Defaulting to UNKNOW.")
    #         self.usage_flags = MftUsageFlags.UNKNOW
    #     self.entry_len = temp[8] #in bytes
    #     self.entry_alloc_len = temp[9] #in bytes
    #     self.base_record_ref, self.base_record_seq = get_file_reference(temp[10])
    #     self.next_attr_id = temp[11]
    #     self.mft_record = temp[12]
    #
    #     if self.fx_offset < MFTHeader.get_header_size():
    #         raise MFTHeaderException("Fix up array begins within the header.", self.mft_record)
    #     if self.entry_len > self.entry_alloc_len:
    #         raise MFTHeaderException("Logical size of the MFT is bigger than MFT allocated size.", self.mft_record)

    @classmethod
    def get_static_content_size(cls):
        '''Return the header size'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object MFTHeader from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of the attribute

        Returns:
            MFTHeader: New object using hte binary stream as source
        '''
        header = cls._REPR.unpack(binary_view[:cls._REPR.size])
        nw_obj = cls()

        if header[0] == b"FILE":
            baad = False
        elif header[0] == b"BAAD":
            baad = True
        else:
            raise HeaderError("Entry has no valid signature.")
        if header[1] < MFTHeader.get_static_content_size(): #header[1] is fx_offset
            raise HeaderError("Fix up array begins within the header.", header[12])
        if header[8] > header[9]: #entry_len > entry_alloc_len
            raise HeaderError("Logical size of the MFT is bigger than MFT allocated size.", header[12])

        file_ref, file_seq = get_file_reference(header[10])

        nw_obj._baad, nw_obj.fx_offset, nw_obj.fx_count, nw_obj.lsn, \
        nw_obj.seq_number, nw_obj.hard_link_count, nw_obj.first_attr_offset, \
        nw_obj.usage_flags, nw_obj._entry_len, nw_obj.entry_alloc_len, \
        nw_obj.base_record_ref, nw_obj.base_record_seq, nw_obj.next_attr_id, \
        nw_obj.mft_record = \
        baad, header[1], header[2], header[3], header[4], \
        header[5], header[6], MftUsageFlags(header[7]), header[8], header[9], \
        file_ref, file_seq, header[11], header[12]

        return nw_obj

    def is_bad_entry(self):
        return self._baad

    def __len__(self):
        '''Returns the logical size of the mft entry'''
        return self._entry_len

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(is_baad={!s}, fx_offset={:#06x}, fx_count={}, lsn={}, seq_number={}, hard_link_count={}, first_attr_offset={}, usage_flags={!s}, entry_len={}, entry_alloc_len={}, base_record_ref={:#x}, base_record_seq={:#x}, next_attr_id={}, mft_record={})'.format(
            self._baad, self.fx_offset, self.fx_count, self.lsn, self.seq_number,
            self.hard_link_count, self.first_attr_offset, self.usage_flags, self._entry_len,
            self.entry_alloc_len, self.base_record_ref, self.base_record_seq, self.next_attr_id,
            self.mft_record)

ResidentAttrHeader = collections.namedtuple("ResidentAttrHeader",
    ["content_len", "content_offset", "indexed_flag"])

#******************************************************************************
# DATA_RUN
#******************************************************************************
# Data runs are part of the non resident header.
class DataRuns():
    _INFO = struct.Struct("<B")

    def __init__(self, runs_view):
        '''Parses and stores the data runs of a non-resident attribute. This can,
        for all intents an purpose, the "content" of an attribute in the view of
        MFT, even if the tru content is somewhere else on the disk.
        The data run structure is stored in a list of tuples, where the first value
        is the length of the data run and the second value is the absolute offset.

        Great resource for explanation and tests:
        https://flatcap.org/linux-ntfs/ntfs/concepts/data_runs.html
        '''
        self.data_runs = [] #lis of tuples
        #TODO create a class for this?

        offset = 0
        previous_dr_offset = 0
        header_size = DataRuns._INFO.size #"header" of a data run is always a byte

        while runs_view[offset] != 0:   #the runlist ends with an 0 as the "header"
            header = DataRuns._INFO.unpack(runs_view[offset:offset+header_size])[0]
            length_len = header & 0x0F
            length_offset = (header & 0xF0) >> 4

            temp_len = offset+header_size+length_len #helper variable just to make things simpler
            dr_length = int.from_bytes(runs_view[offset+header_size:temp_len], "little", signed=False)
            if length_offset: #the offset is relative to the previous data run
                dr_offset = int.from_bytes(runs_view[temp_len:temp_len+length_offset], "little", signed=True) + previous_dr_offset
                previous_dr_offset = dr_offset
            else: #if it is sparse, requires a a different approach
                dr_offset = None
            offset += header_size + length_len + length_offset
            self.data_runs.append((dr_length, dr_offset))

    def __len__(self):
        '''Returns the number of data runs'''
        return len(self.data_runs)

    def __iter__(self):
        '''Return the iterator for the representation of the list.'''
        return iter(self.data_runs)

    def __getitem__(self, index):
        '''Return a specific data run'''
        return self.data_runs[index]

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(data_runs={})'.format(
            self.data_runs)

class NonResidentAttrHeader():
    '''Represents the non-resident header of an attribute.'''
    _REPR = struct.Struct("<2Q2H4x3Q")
    ''' Start virtual cluster number - 8
        End virtual cluster number - 8
        Runlist offset - 2
        Compression unit size - 2
        Padding - 4
        Allocated size of the stream - 8
        Current size of the stream - 8
        Initialized size of the stream - 8
        Data runs - dynamic
    '''

    def __init__(self, header_view, non_resident_offset):
        '''Creates a NonResidentAttrHeader object. header_view is a memoryview
        starting at the beginning of the attribute and the non_resident_offset is
        the size of the AttributeHeader, pointing to where the non resident
        header starts'''
        temp = self._REPR.unpack(header_view[non_resident_offset:non_resident_offset+NonResidentAttrHeader._REPR.size])

        self.start_vcn = temp[0]
        self.end_vcn = temp[1]
        self.rl_offset = temp[2]
        self.compress_usize = temp[3]
        self.alloc_sstream = temp[4]
        self.curr_sstream = temp[5]
        self.init_sstream = temp[6]
        self.data_runs = DataRuns(header_view[self.rl_offset:])

    @classmethod
    def get_header_size(cls):
        '''Return the header size, does not account for the number of data runs'''
        return cls._REPR.size

    def __len__(self):
        '''Returns the logical size of the mft entry'''
        self.entry_len

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(start_vcn={}, end_vcn={}, rl_offset={}, compress_usize={}, alloc_sstream={}, curr_sstream={}, init_sstream={}, data_runs={!s})'.format(
            self.start_vcn, self.end_vcn, self.rl_offset, self.compress_usize, self.alloc_sstream,
            self.curr_sstream, self.init_sstream, self.data_runs)

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

    _ALWAYS_RESIDENT = [AttrTypes.STANDARD_INFORMATION, AttrTypes.FILE_NAME,
        AttrTypes.INDEX_ROOT]

    def __init__(self, header_view):
        '''Creates a header entry with from a memoryview. The memory view must
        start when the first attribute starts and must have all necssary data
        related to resident or non resident headers'''
        temp = self._REPR.unpack(header_view[:self._REPR.size])

        self.attr_type_id = AttrTypes(temp[0])
        self.attr_len = temp[1]
        self.non_resident = bool(temp[2])
        self.name_len = temp[3]
        self.name_offset = temp[4]
        self.flags = AttrFlags(temp[5])
        self.attr_id = temp[6]
        self.resident_header = None
        self.non_resident_header = None
        self.attr_name = None

        if self.name_len:
            self.attr_name = header_view[self.name_offset:self.name_offset+(2*self.name_len)].tobytes().decode("utf_16_le")

        if self.attr_type_id in AttributeHeader._ALWAYS_RESIDENT and self.non_resident:
            MOD_LOGGER.error(f"Attribute {self.attr_type.name} must always be resident")
            raise AttrHeaderException(f"Attribute {self.attr_type.name} is always resident.")

        if not self.non_resident:
            self.resident_header = ResidentAttrHeader._make(self._REPR_RESIDENT.unpack(header_view[self._REPR.size:self._REPR.size + self._REPR_RESIDENT.size]))
        else:
            self.non_resident_header = NonResidentAttrHeader(header_view, self._REPR.size)

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
            self.attr_type_id, self.attr_len, self.non_resident,
            self.name_len, self.name_offset, self.flags, self.attr_id,
            self.resident_header, self.non_resident_header, self.attr_name)

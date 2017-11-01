import struct
from datetime import datetime as _datetime, timedelta as _timedelta
import enum
import collections

class MftHeaderSig(enum.Enum):
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

class MftSignature(enum.Enum):
    FILE = b"FILE"
    BAAD = b"BAAD"
    INDX = b"INDX"

class MftUsageFlags(enum.Enum):
    NOT_USED = 0x0000
    IN_USE = 0x0001
    DIRECTORY = 0x0002
    DIRECTORY_IN_USE = 0x0003

class MFTHeader():
    #TODO create a way of dealing with XP only artefacts
    _REPR = struct.Struct("4s2hQ4h2IQ2hI")

    def __init__(self, header_view):
        temp = self._REPR.unpack(header_view)

        self.signature = MftSignature(temp[0])
        self.fx_offset = temp[1]
        self.fx_count = temp[2]
        self.lsn = temp[3]
        self.seq_number = temp[4]
        self.hard_link_count = temp[5]
        self.first_attr_offset = temp[6]
        self.usage_flags = MftUsageFlags(temp[7])
        self.mft_size = temp[8]
        self.mft_alloc_size = temp[9]
        self.parent_dir = temp[10]
        self.next_attr_id = temp[11]
        self.padding = temp[12]
        self.mft_record = temp[13]

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
        return self.__class__.__name__ + '(signature={!s}, fx_offset={:#06x}, fx_count={}, lsn={}, seq_number={}, hard_link_count={}, first_attr_offset={}, usage_flags={!s}, mft_size={}, mft_alloc_size={}, parent_dir={}, next_attr_id={}, padding={}, mft_record={})'.format(
            self.signature, self.fx_offset, self.fx_count, self.lsn, self.seq_number,
            self.hard_link_count, self.first_attr_offset, self.usage_flags, self.mft_size,
            self.mft_alloc_size, self.parent_dir, self.next_attr_id, self.padding,
            self.mft_record)

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

class AttrNonResident(enum.Enum):
    NO = 0x0
    YES = 0x1

class AttrFlags(enum.Enum):
    NORMAL = 0x0000
    COMPRESSED = 0x0001
    ENCRYPTED = 0x4000
    SPARSE = 0x8000

ResidentAttrHeader = collections.namedtuple("ResidentAttrHeader",
    ["content_len", "content_offset", "indexed_flag"])

NonResidentAttrHeader = collections.namedtuple("NonResidentAttrHeader",
    ["start_vcn", "end_vcn", "rl_offset", "compress_usize", "padding"
    "alloc_sstream", "curr_sstream", "init_sstream"])

class AttributeHeader():
    #TODO create a way of dealing with XP only artefacts
    _REPR = struct.Struct("2I2B3H")
    _REPR_RESIDENT = struct.Struct("IHBx")
    _REPR_NONRESIDENT = struct.Struct("2Q2H4x3Q")

    def __init__(self, header_view):
        temp = self._REPR.unpack(header_view[:self._REPR.size])

        self.attr_type_id = AttrTypes(temp[0])
        self.len_attr = temp[1]
        self.nonresident_flag = AttrNonResident(temp[2])
        self.name_len = temp[3]
        self.name_offset = temp[4]
        self.flags = AttrFlags(temp[5])
        self.attr_id = temp[6]
        self.resident_header = None
        self.non_resident_header = None

        if self.nonresident_flag is AttrNonResident.NO:
            self.resident_header = ResidentAttrHeader._make(self._REPR_RESIDENT.unpack(header_view[self._REPR.size:self._REPR.size + self._REPR_RESIDENT.size]))
        else:
            self.non_resident_header = NonResidentAttrHeader._make(self._REPR_NONRESIDENT.unpack(header_view[self._REPR.size:self._REPR.size+self._REPR_NONRESIDENT.size]))

    @classmethod
    def size(cls):
        '''Return the header size'''
        return cls._REPR.size

    def __len__(self):
        '''Returns the logical size of the mft entry'''
        self.len_attr

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(attr_type_id={!s}, len_attr={}, nonresident_flag={!s}, name_len={}, name_offset={:#06x}, flags={!s}, attr_id={}, resident_header={}, non_resident_header={})'.format(
            self.attr_type_id, self.len_attr, self.nonresident_flag,
            self.name_len, self.name_offset, self.flags, self.attr_id,
            self.resident_header, self.non_resident_header)

class MFTEntry():
    #has 1 MFTHeader
    #has n attribute headers
    #has n attribute content
    #structure mft header -> attr header -> attr content -> attr header -> ...
    def __init__(self, bin_stream):
        '''Expects a writeable array with support to memoryview. Normally
        this would be a bytearray type. Once it has that, it reads the MFT
        and the necessary attributes. This read exactly one entry.
        '''
        self.mft_header = None
        bin_view = memoryview(bin_stream)
        attrs_view = None

        self.mft_header = MFTHeader(bin_view[:MFTHeader.size()])
        if len(bin_stream) != self.mft_header.mft_alloc_size:
            #TODO error handling
            print("EXPECTED MFT SIZE IS DIFFERENT THAN ENTRY SIZE. PROBLEM!")
        self._apply_fixup_array(bin_view)

        attrs_view = bin_view[self.mft_header.first_attr_offset:]
        print(self.mft_header)
        #TODO have a "attribute parser" and a dispatcher?
        self._load_attributes(attrs_view)

        bin_view.release() #release the underlying buffer

    def _apply_fixup_array(self, bin_view):
        '''This function reads the fixup array and apply the correct values
        to the underlying binary stream. This function changes the entries
        in memory.
        '''
        fx_array = bin_view[self.mft_header.fx_offset:self.mft_header.fx_offset+(2 * self.mft_header.fx_count)]
        #the array is composed of the signature + substitutions, so fix that
        fx_len = self.mft_header.fx_count - 1
        #we can infer the sector size based on the size of the mft
        sector_size = int(self.mft_header.mft_alloc_size / fx_len)
        index = 1
        position = (sector_size * index) - 2
        while (position <= self.mft_header.mft_alloc_size):
            if bin_view[position:position+1].tobytes() == fx_array[:1].tobytes():
                #the replaced part must always match the signature!
                bin_view[position:position+1] = fx_array[index * 2:(index * 2) + 1]
            else:
                print("REPLACING WRONG PLACE, STOP MOTHERFUCKER!")
                #TODO error handling
            index += 1
            position = (sector_size * index) - 2

    def _load_attributes(self, attrs_view):
        '''This function receives a view that starts at the first attribute
        until the end of the entry
        '''
        base_size = AttributeHeader.size()
        offset = 0

        while (attrs_view[offset:offset+4] != b'\xff\xff\xff\xff'):
            #pass all the information to the attr, as we don't know how
            #much content the attribute has
            attr = AttributeHeader(attrs_view[offset:])
            print(attr)
            offset += attr.len_attr



        '''
            attr_offset = mft_header.offset_first_attr
            i = 0
            while (bin_view[attr_offset:attr_offset+4] != b'0xffffffff'):
                attr_offset += read_mft_attribute(bin_view, attr_offset).len_attr
                if i > 2:
                    break
                else:
                    i += 1
        '''


class MFT():
    '''This class represents a MFT file. It has a bunch of MFT entries
    that have been parsed
    '''

    def __init__(self, file_pointer, size=0, use_cores=1):
        '''The initialization process takes a file like object "file_pointer"
        and loads it in the internal structures. "use_cores" can be definied
        if multiple cores are to be used. The "size" argument is the size
        of the MFT entries. If not provided, the class will try to auto detect
        it.
        '''
        self.mft_entry_size = size

        data_buffer = 0

        if not self.mft_entry_size:
            self.mft_entry_size = self._find_mft_size(file_pointer)

        #TODO test and verify what happens with really big files? overflow?
        file_pointer.seek(0, 2)
        end = int(file_pointer.tell() / self.mft_entry_size)
        if (file_pointer.tell() % self.mft_entry_size):
            #TODO possible error handling (file size not multiple of mft size)
            print("FILE SIZE NOT MULITPLE OF MFT ENTRY SIZE, POSSIBLE PROBLEM")
        file_pointer.seek(0, 0)
        data_buffer = bytearray(self.mft_entry_size)
        for i in range(0, end):
            file_pointer.readinto(data_buffer)
            #TODO store this somewhere (list?)
            MFTEntry(data_buffer)
            break
        print(file_pointer.tell())

        #TODO multiprocessing, see below
        '''
        A deeper study/test is necessary before implementing multiprocess.
        With the standard queue model, copies of the data have to be made
        for queue input as they will be consumed. This generates lots of memory
        allocation calls and possible pickle of the data. As the processing itself
        is not so great, mostly memory manipulation/interpretation, the amount
        of calls might fuck things up. A reasonable approach would be using
        Managers and create a "shared variables", an array with multiple buffers
        and updating the buffers as they are processed. This will require some
        fine tuning of how/when the shared buffers are accessed and might become
        too complex for maintenance. So, options:
        * Use a standard queue and create copies of data read from the file
        * Use a shared queue/list and think about a way of sync things without
         messing it up
        * Actually parallelize the access to the file, passing each thread their
         "limits", this might screw IO performance... badly...
        * Don't add multiprocessing and keep using a single buffer

        The managers shit:
            https://docs.python.org/3/library/multiprocessing.html?highlight=queue#multiprocessing-managers
            https://stackoverflow.com/questions/11196367/processing-single-file-from-multiple-processes-in-python
        '''

    def _find_mft_size(self, file_object):
        sizes = [1024, 4096, 512, 2048]
        sigs = [member.value for name, member in MftSignature.__members__.items()]

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

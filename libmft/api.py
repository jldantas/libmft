'''
#TODO
-Definition of the API
This module is reponsible for the main parts that are exposed to the calling application.

- Structure of the API

The MFT has a number of different entries of type MFTEntry, these entries
have a header (MFTHeader) and a 'n' number of attributes and the attributes
have a header and a content. A rough of diagram can be seen below:

+-----+
| MFT |
+--+--+
   |     +----------+
   +-----+ MFTEntry |          +--------+
   |     +----------+    +-----+ Header |
   |     +----------+    |     +--------+          +--------+
   +-----+ MFTEntry +----+                      +--+ Header |
   |     +----------+    |      +------------+  |  +--------+
   |          X          +------+ Attributes +--+
   |                     |      +------------+  |  +---------+
   |          X          |            X         +--+ Content |
   |                     |                         +---------+
   |          X          |            X
   |                     |
   |     +----------+    |      +------------+
   +-----+ MFTEntry |    +------+ Attributes |
         +----------+           +------------+

-- MFT - Represents the MFT
-- MFTEntry - Represents one entry from the logical perspective, i.e., even if
    the attributes are spread across multiple entry in the file, they will be
    organized under the base entry
-- MFTHeader - Represents the header of the MFT entry
-- Attribute - Represents one attribute
-- AttributeHeader - Represents the header of the attribute, including if it is
    resident or non-resident
-- The content depends on the type of attribute

- Considerations

While a entry provides a logical MFT entry, a logical MFT entry may contain
multiple logical entries (hard links and data streams) which means that one entry
needs to be correctly processed to show all the data
'''
import struct
import enum
import collections
import logging

from itertools import chain as _chain
from collections import defaultdict as _defaultdict
from functools import lru_cache
from operator import itemgetter as _itemgetter

from libmft.util.functions import convert_filetime, apply_fixup_array, flatten, \
    get_file_size as _get_file_size, is_related as _is_related, get_file_reference, \
    exits_bisect
from libmft.flagsandtypes import MftSignature, AttrTypes, MftUsageFlags
from libmft.attrcontent import StandardInformation, FileName, IndexRoot, Data, \
    AttributeList, Bitmap, ObjectID, VolumeName, VolumeInformation, ReparsePoint, \
    EaInformation, LoggedToolStream
from libmft.headers import MFTHeader, ResidentAttrHeader, NonResidentAttrHeader,  \
    AttributeHeader, DataRuns
from libmft.exceptions import MFTEntryException, FixUpError, DataStreamError

MOD_LOGGER = logging.getLogger(__name__)

class Datastream():
    '''Represents one datastream for a entry. This datastream has all the necessary
    information, for example, name, size, allocated size, number of clusters, etc.
    The data runs, if loaded, are guaranteed to be in order.

    The main idea is that this way we can save memory space and normalize
    access to a data Independently if it is resident or non resident.
    '''
    def __init__(self, name=None):
        '''Initialize on datastream. The only parameter accepted is the
        name of the datastream.'''
        #we don't need to save the compression usize because we are unable to access the rest of the disk
        self.name = name
        self.size = 0 #logical size
        self.alloc_size = 0 #allocated size
        self.cluster_count = 0
        self._data_runs = None #data runs only exist if the attribute is non resident
        self._content = None
        self._data_runs_sorted = False

    def add_data_attribute(self, data_attr):
        '''Interprets a DATA attribute and add it to the datastream.'''
        if data_attr.header.attr_type_id is not AttrTypes.DATA:
            raise DataStreamError("Invalid attribute. A Datastream deals only with DATA attributes")
        if data_attr.header.attr_name != self.name:
            raise DataStreamError("Data from a different stream 'f{data_attr.header.attr_name}' cannot be add to this stream")

        if data_attr.header.is_non_resident():
            nonr_header = data_attr.header.non_resident_header
            if self._data_runs is None:
                self._data_runs = []
            if nonr_header.end_vcn > self.cluster_count:
                self.cluster_count = nonr_header.end_vcn
            if not nonr_header.start_vcn: #start_vcn == 0
                self.size = nonr_header.curr_sstream
                self.alloc_size = nonr_header.alloc_sstream
            self._data_runs.append((nonr_header.start_vcn, nonr_header.end_vcn, nonr_header.data_runs))
            self._data_runs_sorted = False
        else: #if it is resident
            self.size = self.alloc_size = data_attr.header.resident_header.content_len
            self._pending_processing = None
            #respects mft_config["load_data"]
            self._content = data_attr.content.content

        #print(self)

    def add_from_datastream(self, source_ds):
        if source_ds.name != self.name:
            raise DataStreamError("Data from a different stream 'f{source_ds.name}' cannot be add to this stream")
        if self._data_runs is None:
            raise DataStreamError("Cannot add data to a resident datastream.")
        if self.cluster_count < source_ds.cluster_count:
            self.cluster_count = source_ds.cluster_count
        if self.size == 0 and source_ds.size:
            self.size = source_ds.size
            self.alloc_size = source_ds.alloc_size
        if source_ds._data_runs:
            self._data_runs += source_ds._data_runs
            self._data_runs_sorted = False

    def get_dataruns(self):
        if self._data_runs is None:
            raise DataStreamError("Resident datastream don't have dataruns")
        if not self._data_runs_sorted:
            self._data_runs.sort(key=_itemgetter(0))

        return [data[2] for data in self._data_runs]

    def is_resident(self):
        if self._data_runs is None:
            return True
        else:
            return False

    def __eq__(self, cmp):
        if self.name == cmp.name:
            return True
        else:
            return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(name={}, size={}, alloc_size={}, cluster_count={}, _data_runs={}, _content={})'.format(
            self.name, self.size, self.alloc_size, self.cluster_count, self._data_runs, self._content)

class Attribute():
    '''Represents an attribute, header and content. Independently the type of
    attribute'''
    def __init__(self, header=None, content=None):
        '''Creates an Attribute object. The content variable is expected to be assigned
        only in case of a resident attribute. It is recommended to use the
        "create_from_binary" function

        Args:
            header (AttributeHeader) - The header of the attribute
            content (Variable) - The content of the attribute. Depends on the type
                of the attribute.
        '''
        self.header = header
        self.content = content

    @classmethod
    def create_from_binary(cls, mft_config, binary_view):
        header = AttributeHeader.create_from_binary(mft_config, binary_view)
        content = None

        if not header.is_non_resident():
            offset = header.resident_header.content_offset
            length = header.resident_header.content_len
            attr_config = mft_config["attributes"]

            if attr_config["file_name"] and header.attr_type_id is AttrTypes.FILE_NAME:
                content = FileName.create_from_binary(binary_view[offset:offset+length])
            elif attr_config["std_info"] and header.attr_type_id is AttrTypes.STANDARD_INFORMATION:
                content = StandardInformation.create_from_binary(binary_view[offset:offset+length])
            elif attr_config["idx_root"] and header.attr_type_id is AttrTypes.INDEX_ROOT:
                content = IndexRoot.create_from_binary(binary_view[offset:offset+length])
            elif attr_config["attr_list"] and header.attr_type_id is AttrTypes.ATTRIBUTE_LIST:
                content = AttributeList.create_from_binary(binary_view[offset:offset+length])
            elif mft_config["datastreams"]["load_content"] and header.attr_type_id is AttrTypes.DATA:
                content = Data(binary_view[offset:offset+length])
            elif attr_config["object_id"] and header.attr_type_id is AttrTypes.OBJECT_ID:
                content = ObjectID.create_from_binary(binary_view[offset:offset+length])
            elif attr_config["bitmap"] and header.attr_type_id is AttrTypes.BITMAP:
                content = Bitmap(binary_view[offset:offset+length])
            elif attr_config["ea_info"] and header.attr_type_id is AttrTypes.EA_INFORMATION:
                content = EaInformation(binary_view[offset:offset+length])
            elif attr_config["log_tool_str"] and header.attr_type_id is AttrTypes.LOGGED_TOOL_STREAM:
                content = LoggedToolStream(binary_view[offset:offset+length])
            elif attr_config["reparse"] and header.attr_type_id is AttrTypes.REPARSE_POINT:
                content = ReparsePoint.create_from_binary(binary_view[offset:offset+length])
            elif attr_config["vol_name"] and header.attr_type_id is AttrTypes.VOLUME_NAME:
                content = VolumeName.create_from_binary(binary_view[offset:offset+length])
            elif attr_config["vol_info"] and header.attr_type_id is AttrTypes.VOLUME_INFORMATION:
                content = VolumeInformation.create_from_binary(binary_view[offset:offset+length])
            else:
                #print(self.header.attr_type_id)
                #TODO log/error when we don't know how to treat an attribute
                pass

        return cls(header, content)

    def is_non_resident(self):
        '''Helper function to check if an attribute is resident or not. Returns
        True if it is resident, otherwise returns False'''
        return self.header.is_non_resident()

    def __len__(self):
        '''Returns the length of the attribute, in bytes'''
        return len(self.header)

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(header={}, content={})'.format(
            self.header, self.content)

class MFTEntry():
    '''Represents one LOGICAL MFT entry. That means the entry is the base entry
    and all the attributes that are spread across multiple physical entries are
    aggregated in the base entry.
    '''

    def __init__(self, header=None, attrs=None):
        '''Creates a MFTEntry object.

        Args:
            header (MFTHeader) - The header of the attribute
            attrs (`list` of Attribute) - list of Attributes that are related to
                this entry
            slack (binary string) - the binary stream with the slack data
        '''
        self.header, self.attrs = header, attrs
        self.data_streams = None
        #--------------


    @classmethod
    def create_from_binary(cls, mft_config, binary_data, entry_number):
        #TODO test carefully how to find the correct index entry, specially with NTFS versions < 3
        '''Creates a MFTEntry from a binary stream. It correctly process
        the binary data extracting the MFTHeader, all the attributes and the
        slack information from the binary stream.

        The binary data WILL be changed to apply the fixup array.

        Args:
            mft_config (dict) - A dictionary with the configuration with what to load
            binary_data (bytearray) - A binary stream with the data to extract.
                This has to be a writeable and support the memoryview call
            entry_number (int) - The entry number for this entry

        Returns:
            MFTEntry: If the object is empty, returns None, otherwise, new object MFTEntry
        '''
        bin_view = memoryview(binary_data)
        entry = None

        #no check is performed if an entry is empty
        #the _MFTEntryStub code SHOULD detect if there is an empty entry
        header = MFTHeader.create_from_binary(bin_view[:MFTHeader.get_static_content_size()])
        entry = cls(header, {})
        entry.data_streams = []

        if header.mft_record != entry_number:
            MOD_LOGGER.warning(f"The MFT entry number doesn't match. {entry_number} != {header.mft_record}")
        if len(binary_data) != header.entry_alloc_len:
            MOD_LOGGER.error(f"Expected MFT size is different than entry size.")
            raise MFTEntryException("Expected MFT size is different than entry size.", entry_number)
        if mft_config["apply_fixup_array"]:
            try:
                apply_fixup_array(bin_view, header.fx_offset, header.fx_count, header.entry_alloc_len)
            except FixUpError as e:
                e.update_entry_binary(binary_data)
                e.update_entry_number(entry_number)
                raise

        if mft_config["attributes"]["enable"] or mft_config["datastreams"]["enable"]:
            entry._load_attributes(mft_config, bin_view[header.first_attr_offset:])

        bin_view.release() #release the underlying buffer

        return entry

    def _find_datastream(self, name):
        for stream in self.data_streams: #search to see if this is a new datastream or a known one
            if stream.name == name:
                return stream
        return None

    def _add_datastream(self, data_attr):
        attr_name = data_attr.header.attr_name

        stream = self._find_datastream(attr_name)
        if stream is None:
            stream = Datastream(attr_name)
            self.data_streams.append(stream)
        stream.add_data_attribute(data_attr)

        #TODO datastream loads itself, we also need to copy a data stream


    def _add_attribute(self, attr):
        '''Adds one attribute to the list of attributes. Checks if the the entry
        already has another entry of the attribute and if not, creates the necessary
        structure'''
        if attr.header.attr_type_id not in self.attrs:
            self.attrs[attr.header.attr_type_id] = []
        self.attrs[attr.header.attr_type_id].append(attr)

    def _load_attributes(self, mft_config, attrs_view):
        '''This function receives a view that starts at the first attribute
        until the end of the entry
        '''
        offset = 0

        while (attrs_view[offset:offset+4] != b'\xff\xff\xff\xff'):
            #pass all the information to the attr, as we don't know how
            #much content the attribute has
            attr = Attribute.create_from_binary(mft_config, attrs_view[offset:])
            if not attr.header.attr_type_id is AttrTypes.DATA:
                self._add_attribute(attr)
            else:
                self._add_datastream(attr)
            offset += len(attr)

    def merge_entries(self, source_entry):
        '''Merge one entry attributes and datastreams with the current entry.
        '''
        #TODO I really don't like this. We are spending cycles to load things that are going to be discarted. Check another way.
        #copy the attributes
        for list_attr in source_entry.attrs.values():
            for attr in list_attr:
                self._add_attribute(attr)
        #copy data_streams
        for stream in source_entry.data_streams:
            dest_stream = self._find_datastream(stream.name)
            if dest_stream is not None:
                dest_stream.add_from_datastream(stream)
            else:
                self.data_streams.append(stream)

    def get_attributes(self, attr_type):
        '''Returns a list with one or more attributes of type "attr_type", in
        case they exist, otherwise, returns None. The attr_type must be a AttrTypes enum.'''
        if attr_type in self.attrs:
            return self.attrs[attr_type]
        else:
            return None

    def get_data_size(self, ads_name=None):
        '''Returns the size of the data or an ads. The ads has to be the name of the file'''
        data_attrs = self.get_attributes(AttrTypes.DATA)
        data_size = 0

        if data_attrs is not None:
            #select the correct attributes of the file
            if ads_name is None:
                relevant_attr = [a for a in data_attrs if a.header.attr_name is None]
            else:
                relevant_attr = [a for a in data_attrs if a.header.attr_name == ads_name]
            #once we the right attributes, process and find the size
            for attr in relevant_attr:
                if attr.is_non_resident():
                    if not attr.header.non_resident_header.start_vcn:
                        data_size = attr.header.non_resident_header.curr_sstream
                        break
                else:
                    data_size = len(attr.content)
                    break

        return data_size

    def get_datastream_names(self):
        ads_names = set()

        data_attrs = self.get_attributes(AttrTypes.DATA)
        if data_attrs is not None:
            for data_attr in data_attrs:
                ads_names.add(data_attr.header.attr_name)

        if len(ads_names):
            return ads_names
        else:
            return None

    def has_ads(self):
        data_attrs = self.get_attributes(AttrTypes.DATA)
        if data_attrs is not None:
            for a in data_attrs:
                if a.header.attr_name:
                    return True
            return False
        else:
            return False

    def get_names(self):
        names = set()

        attrs = self.get_attributes(AttrTypes.FILE_NAME)
        if attrs is not None:
            names = {attr.content.name for attr in attrs}

        return names

    def is_deleted(self):
        if self.header.usage_flags & MftUsageFlags.IN_USE:
            return False
        else:
            return True

    def is_directory(self):
        if self.header.usage_flags & MftUsageFlags.DIRECTORY:
            return True
        else:
            return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        #TODO print the slack?
        return self.__class__.__name__ + '(header={}, attrs={}, data_stream={})'.format(
            self.header, self.attrs, self.data_streams)

def is_related2(parent_entry, child_entry):
    '''This function checks if a child entry is related to the parent entry.
    This is done by comparing the reference and sequence numbers.'''
    if parent_entry.mft_record == child_entry.base_record_ref and \
       parent_entry.seq_number == child_entry.base_record_seq:
        return True
    else:
        return False

class _MFTEntryStub():
    #TODO create a way of dealing with XP only artefacts
    _REPR = struct.Struct("<16xH14xQ")
    ''' Ignore the first 16 bytes (Signature, fix up array offset, count and
            lsn)
        Sequence number - 2
        Ignore the next 14 bytes (hard link count, offset to 1st attr, usage flags,
            mft logical size and physical size)
        Base record # - 8
    '''
    def __init__(self, content=(None,)*4):
        self.mft_record, self.seq_number, self.base_record_ref, \
        self.base_record_seq = content

    @classmethod
    def load_from_file_pointer(cls, binary_stream, record_n):
        nw_obj = None

        if binary_stream[0:4] != b"\x00\x00\x00\x00": #test if the entry is empty
            #the position of the data we are interested is always (or should) happen before the
            #first fixup value, so no need to apply it
            seq_number, ref = cls._REPR.unpack(binary_stream)
            file_ref, file_seq = get_file_reference(ref)
            nw_obj = cls()

            nw_obj.mft_record, nw_obj.seq_number, nw_obj.base_record_ref, \
            nw_obj.base_record_seq = record_n, seq_number, file_ref, file_seq
        else:
            MOD_LOGGER.debug(f"Entry {record_n} is empty.")

        return nw_obj

    @classmethod
    def get_static_content_size(cls):
        '''Returns the static size of the content never taking in consideration
        variable fields, for example, names.

        Returns:
            int: The size of the content, in bytes
        '''
        return cls._REPR.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        #TODO print the slack?
        return self.__class__.__name__ + '(mft_record={}, seq_number={}, base_record_ref={}, base_record_seq={})'.format(
            self.mft_record, self.seq_number, self.base_record_ref, self.base_record_seq)

class MFT():
    '''This class represents a MFT file. It has a bunch of MFT entries
    that have been parsed
    '''
    mft_config = {"entry_size" : 0, #0 for autodetect
                  "apply_fixup_array" : True,
                  "attributes" : {},
                  "datastreams": {}
                 }
    mft_config["attributes"] = {"enable" : True,
                                "load_dataruns" : True, #dataruns are part of the attribute header
                                "std_info" : True,
                                "attr_list" : True,
                                "file_name" : True,
                                "object_id" : True,
                                "sec_desc" : True,
                                "vol_name" : True,
                                "vol_info" : True,
                                "idx_root" : True,
                                "idx_alloc" : True,
                                "bitmap" : True,
                                "reparse" : True,
                                "ea_info" : True,
                                "ea" : True,
                                "log_tool_str" : True
                               }
    mft_config["datastreams"] = {"enable" : True,
                                 "load_content" : True
                                }

    def __init__(self, file_pointer, mft_config=None):
        #TODO redo documentation
        '''The initialization process takes a file like object "file_pointer"
        and loads it in the internal structures. "use_cores" can be definied
        if multiple cores are to be used. The "size" argument is the size
        of the MFT entries. If not provided, the class will try to auto detect
        it.
        '''
        self.file_pointer = file_pointer
        self.mft_config = mft_config if mft_config is not None else MFT.mft_config
        self.mft_entry_size = self.mft_config["entry_size"]
        self._entries_parent_child = _defaultdict(list) #holds the relation ship between parent and child
        self._empty_entries = set() #holds the empty entries
        self._entries_child_parent = {} #holds the relation between child and parent
        self._number_valid_entries = 0

        if not self.mft_entry_size: #if entry size is zero, try to autodetect
            self.mft_entry_size = MFT._find_mft_size(file_pointer)

        self._load_stub_info()

    def _load_stub_info(self):
        '''Load the minimum amount of information related to a MFT. This allows
        the library to map all the relations between the entries, so the information
        is complete when dealing with the entries.

        This is necessary because the ATTRIBUTE_LIST can be non-resident and, in
        this case, we can't find the relationship using only the entry.
        '''
        mft_entry_size = self.mft_entry_size
        read_size = _MFTEntryStub.get_static_content_size()
        data_buffer = bytearray(read_size)
        temp = []

        #loads minimum amount of data from the file for now
        MOD_LOGGER.info("Loading basic info from file...")
        for i in range(0, _get_file_size(self.file_pointer), mft_entry_size):
            mft_record_n = int(i/mft_entry_size)    #calculate which is the entry number
            self.file_pointer.seek(i)
            self.file_pointer.readinto(data_buffer)
            stub = _MFTEntryStub.load_from_file_pointer(data_buffer, mft_record_n)
            temp.append(stub)
        #from the information loaded, find which entries are related and the one that are empty
        MOD_LOGGER.info("Mapping related entries...")
        for i, stub in enumerate(temp):
            if stub is not None:
                if not stub.base_record_ref:
                    self._number_valid_entries += 1
                else:
                    if is_related2(temp[stub.base_record_ref], stub): #stub.base_record_ref is not 0
                        self._entries_parent_child[stub.base_record_ref].append(stub.mft_record)
                        self._entries_child_parent[stub.mft_record] = stub.base_record_ref
            else:
                self._empty_entries.add(i)

    def _read_full_entry(self, entry_number):
        if entry_number in self._entries_parent_child:
            extras = self._entries_parent_child[entry_number]
        else:
            extras = []
        entry = None
        binary = bytearray(self.mft_entry_size)

        self.file_pointer.seek(self.mft_entry_size * entry_number)
        self.file_pointer.readinto(binary)
        entry = MFTEntry.create_from_binary(self.mft_config, binary, entry_number)
        for number in extras:
            self.file_pointer.seek(self.mft_entry_size * number)
            self.file_pointer.readinto(binary)
            temp_entry = MFTEntry.create_from_binary(self.mft_config, binary, number)
            #print(temp_entry)
            entry.merge_entries(temp_entry)

        return entry

    def __iter__(self):
        returned = 0
        #mft_entry_size, number_valid_entries _empty_entries = self._empty_entries

        for i in range(0, _get_file_size(self.file_pointer), self.mft_entry_size):
            mft_record_n = int(i/self.mft_entry_size)
            if returned >= self._number_valid_entries:
                break
            if mft_record_n in self._empty_entries or mft_record_n in self._entries_child_parent:
                continue
            else:
                returned += 1
                yield self[mft_record_n]


    @lru_cache(128)
    def __getitem__(self, index):
        '''Return the specific MFT entry. In case of an empty MFT, it will return
        None'''
        search_for = index
        if search_for in self._empty_entries:
            raise ValueError
        if search_for in self._entries_child_parent:
            raise ValueError
            #search_for = self._entries_child_parent[search_for]

        return self._read_full_entry(search_for)


    def __len__(self):
        return self._number_valid_entries

    @staticmethod
    def _find_mft_size(file_object):
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

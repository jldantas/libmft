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

from libmft.util.functions import convert_filetime, apply_fixup_array, flatten, \
    get_file_size as _get_file_size, is_related as _is_related, get_file_reference, \
    exits_bisect
from libmft.flagsandtypes import MftSignature, AttrTypes, MftUsageFlags
from libmft.attrcontent import StandardInformation, FileName, IndexRoot, Data, \
    AttributeList, Bitmap, ObjectID, VolumeName, VolumeInformation, ReparsePoint, \
    EaInformation, LoggedToolStream
from libmft.headers import MFTHeader, ResidentAttrHeader, NonResidentAttrHeader,  \
    AttributeHeader, DataRuns
from libmft.exceptions import MFTEntryException, FixUpError

MOD_LOGGER = logging.getLogger(__name__)

class Datastream():
    def __init__(self, name=None):
        #we don't need to save the compression usize because we are unable to access the rest of the disk
        self.name = name
        self.size = 0 #logical size
        self.alloc_size = 0 #allocated size
        self.cluster_count = 0
        self._pending_processing = {}
        self._data_runs = []
        self._content = None


    def add_data_attribute(self, data_attr):
        #TODO check if the attribute is really data type
        #TODO check if the name is correct

        if data_attr.header.attr_type_id is not AttrTypes.DATA:
            pass
        if data_attr.header.attr_name != self.name:
            pass

        if data_attr.header.is_non_resident():
            print(data_attr.header.non_resident_header)
            nonr_header = data_attr.header.non_resident_header
            #TODO instead of just creating a structure, see if it is okay first
            self._pending_processing[nonr_header.start_vcn] = (nonr_header.end_vcn, nonr_header.data_runs)
            if not nonr_header.start_vcn:
                self.cluster_count = -1
                self.size = nonr_header.curr_sstream
                self.alloc_size = nonr_header.alloc_sstream
            self._collapse()
        else: #if it is resident
            self.size = self.alloc_size = data_attr.header.resident_header.content_len
            self._data_runs = None
            self._pending_processing = None
            #respects mft_config["load_data"]
            self._content = data_attr.content.content

        #print(self)


    def _collapse(self):

        changed = True

        #print(self._pending_processing)

        while changed:
            changed = False
            remove = []
            for start_vcn, (end_vcn, dataruns) in self._pending_processing.items():
                if start_vcn == self.cluster_count + 1:
                    self.cluster_count = end_vcn
                    self._data_runs.append(dataruns)
                    remove.append(start_vcn)
                    changed = True

            for vcn in remove:
                del(self._pending_processing[vcn])

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
        return self.__class__.__name__ + '(name={}, size={}, alloc_size={}, cluster_count={}, _pending_processing={}, _data_runs={}, _content={})'.format(
            self.name, self.size, self.alloc_size, self.cluster_count, self._pending_processing, self._data_runs, self._content)

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
        #print(header)
        content = None

        if not header.is_non_resident():
            offset = header.resident_header.content_offset
            length = header.resident_header.content_len

            if mft_config["load_file_name"] and header.attr_type_id is AttrTypes.FILE_NAME:
                content = FileName.create_from_binary(binary_view[offset:offset+length])
            elif mft_config["load_std_info"] and header.attr_type_id is AttrTypes.STANDARD_INFORMATION:
                content = StandardInformation.create_from_binary(binary_view[offset:offset+length])
            elif mft_config["load_idx_root"] and header.attr_type_id is AttrTypes.INDEX_ROOT:
                content = IndexRoot.create_from_binary(binary_view[offset:offset+length])
            elif mft_config["load_attr_list"] and header.attr_type_id is AttrTypes.ATTRIBUTE_LIST:
                content = AttributeList.create_from_binary(binary_view[offset:offset+length])
            elif mft_config["load_data"] and header.attr_type_id is AttrTypes.DATA:
                content = Data(binary_view[offset:offset+length])
            elif mft_config["load_oject_id"] and header.attr_type_id is AttrTypes.OBJECT_ID:
                content = ObjectID.create_from_binary(binary_view[offset:offset+length])
            elif mft_config["load_bitmap"] and header.attr_type_id is AttrTypes.BITMAP:
                content = Bitmap(binary_view[offset:offset+length])
            elif mft_config["load_ea_info"] and header.attr_type_id is AttrTypes.EA_INFORMATION:
                content = EaInformation(binary_view[offset:offset+length])
            elif mft_config["load_log_tool_str"] and header.attr_type_id is AttrTypes.LOGGED_TOOL_STREAM:
                content = LoggedToolStream(binary_view[offset:offset+length])
            elif mft_config["load_reparse"] and header.attr_type_id is AttrTypes.REPARSE_POINT:
                content = ReparsePoint.create_from_binary(binary_view[offset:offset+length])
            elif mft_config["load_vol_name"] and header.attr_type_id is AttrTypes.VOLUME_NAME:
                content = VolumeName.create_from_binary(binary_view[offset:offset+length])
            elif mft_config["load_vol_info"] and header.attr_type_id is AttrTypes.VOLUME_INFORMATION:
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

    def __init__(self, header=None, attrs=None, slack=None):
        '''Creates a MFTEntry object.

        Args:
            header (MFTHeader) - The header of the attribute
            attrs (`list` of Attribute) - list of Attributes that are related to
                this entry
            slack (binary string) - the binary stream with the slack data
        '''
        self.header, self.attrs, self.slack = header, attrs, slack

        #--------------
        self.data_streams = None

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

        if bin_view[0:4] != b"\x00\x00\x00\x00": #test if the entry is empty
            header = MFTHeader.create_from_binary(bin_view[:MFTHeader.get_static_content_size()])
            entry = cls(header, {})

            #-----------------
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

            if mft_config["load_attributes"]:
                entry._load_attributes(mft_config, bin_view[header.first_attr_offset:])
            if mft_config["load_slack"]:
                entry.slack = bin_view[len(header):].tobytes()
        else:
            MOD_LOGGER.debug(f"Entry {entry_number} is empty.")
        bin_view.release() #release the underlying buffer

        return entry

    def _add_datastream(self, data_attr):
        attr_name = data_attr.header.attr_name
        found = False

        for stream in self.data_streams:
            if stream.name == attr_name:
                stream.add_data_attribute(data_attr)
                found = True
                break

        if not found:
            nw_data_stream = Datastream(attr_name)
            nw_data_stream.add_data_attribute(data_attr)
            self.data_streams.append(nw_data_stream)

        #TODO datastream loads itself, we also need to copy a data stream


    def _add_attribute(self, attr):
        '''Adds one attribute to the list of attributes. Checks if the the entry
        already has another entry of the attribute and if not, creates the necessary
        structure'''
        if attr.header.attr_type_id is AttrTypes.DATA:
            self._add_datastream(attr)
            #TODO remve the rest of the if, it is test only
            # if attr.header.attr_type_id not in self.attrs:
            #     self.attrs[attr.header.attr_type_id] = []
            # self.attrs[attr.header.attr_type_id].append(attr)
        else:
            if attr.header.attr_type_id not in self.attrs:
                self.attrs[attr.header.attr_type_id] = []
            self.attrs[attr.header.attr_type_id].append(attr)



    # def _add_attribute(self, attr):
    #     '''Adds one attribute to the list of attributes. Checks if the the entry
    #     already has another entry of the attribute and if not, creates the necessary
    #     structure'''
    #     if attr.header.attr_type_id not in self.attrs:
    #         self.attrs[attr.header.attr_type_id] = []
    #     if attr.header.attr_type_id is not AttrTypes.DATA:
    #         self.attrs[attr.header.attr_type_id].append(attr)
    #     #let's treat data attributes different, in theory, saves memory
    #     else:
    #         #TODO consider saving the vcns and corelating with the position of the clusters
    #         found = False
    #         for data_attr in self.attrs[AttrTypes.DATA]:
    #             if data_attr.header.attr_id == attr.header.attr_id:
    #                 found = True
    #                 dest_non_resident = data_attr.header.non_resident_header
    #                 src_non_resident = attr.header.non_resident_header
    #                 if not src_non_resident.start_vcn: #if it is 0, we get more info
    #                     dest_non_resident.compress_usize, dest_non_resident.alloc_sstream, \
    #                     dest_non_resident.curr_sstream, dest_non_resident.init_sstream \
    #                      =  src_non_resident.compress_usize, src_non_resident.alloc_sstream, \
    #                         src_non_resident.curr_sstream, src_non_resident.init_sstream
    #                 dest_non_resident.start_vcn = min(dest_non_resident.start_vcn, src_non_resident.start_vcn)
    #                 dest_non_resident.end_vcn = max(dest_non_resident.end_vcn, src_non_resident.end_vcn)
    #                 #join the data runs
    #                 if dest_non_resident.data_runs is not None: #if there is and the source also has, merge
    #                     if src_non_resident.data_runs is not None:
    #                         dest_non_resident.data_runs += src_non_resident.data_runs
    #                 else: #if there is no data run, we can just copy it
    #                     dest_non_resident.data_runs = src_non_resident.data_runs
    #         if not found:
    #             self.attrs[attr.header.attr_type_id].append(attr)

    def _load_attributes(self, mft_config, attrs_view):
        '''This function receives a view that starts at the first attribute
        until the end of the entry
        '''
        offset = 0

        while (attrs_view[offset:offset+4] != b'\xff\xff\xff\xff'):
            #pass all the information to the attr, as we don't know how
            #much content the attribute has
            attr = Attribute.create_from_binary(mft_config, attrs_view[offset:])
            self._add_attribute(attr)
            offset += len(attr)

    # def get_logical_files(self):
    #     import itertools #move this
    #
    #     files = []
    #     fn_attrs = self.get_attributes(AttrTypes.FILE_NAME)
    #
    #     if fn_attrs is not None:
    #         for itertools.groupby(fn_attrs, )
    #         for i1, i2 in itertools.combinations(fn_attrs, 2)
    #         fn_info = [(i, fn.attr_id, fn.content.parent_ref, fn.content.parent_seq) for i, fn in enumerate(fn_attrs)]




    def copy_attributes(self, source_entry):
        for key, list_attr in source_entry.attrs.items():
            for attr in list_attr:
                self._add_attribute(attr)

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
        return self.__class__.__name__ + '(header={}, attrs={})'.format(
            self.header, self.attrs)

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
    mft_config = {"entry_size" : 0,
                  "apply_fixup_array" : True,
                  "load_attributes" : True,
                  "load_slack" : True,
                  "load_dataruns" : True,
                  "load_std_info" : True,
                  "load_attr_list" : True,
                  "load_file_name" : True,
                  "load_oject_id" : True,
                  "load_sec_desc" : True,
                  "load_vol_name" : True,
                  "load_vol_info" : True,
                  "load_data" : True,
                  "load_idx_root" : True,
                  "load_idx_alloc" : True,
                  "load_bitmap" : True,
                  "load_reparse" : True,
                  "load_ea_info" : True,
                  "load_ea" : True,
                  "load_log_tool_str" : True
                  }

    def __init__(self, file_pointer, mft_config=None):
        '''The initialization process takes a file like object "file_pointer"
        and loads it in the internal structures. "use_cores" can be definied
        if multiple cores are to be used. The "size" argument is the size
        of the MFT entries. If not provided, the class will try to auto detect
        it.
        '''
        self.file_pointer = file_pointer
        self.mft_config = mft_config if mft_config is not None else MFT.mft_config
        self.mft_entry_size = self.mft_config["entry_size"]
        self._entries_parent_child = _defaultdict(list)
        self._empty_entries = set()
        self._entries_child_parent = {}

        if not self.mft_entry_size: #if entry size is zero, try to autodetect
            self.mft_entry_size = MFT._find_mft_size(file_pointer)

        self._load_stub_info()

    def _load_stub_info(self):
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
                if stub.base_record_ref and is_related2(temp[stub.base_record_ref], stub): #stub.base_record_ref is not 0
                    self._entries_parent_child[stub.base_record_ref].append(stub.mft_record)
                    self._entries_child_parent[stub.mft_record] = stub.base_record_ref
            else:
                #self._empty_entries.append(i)
                self._empty_entries.add(i)

    def _read_full_entry(self, entry_number):
        if entry_number in self._entries_parent_child:
            extras = self._entries_parent_child[entry_number]
        else:
            extras = []

        for number in _chain([entry_number], extras):
            print(number)

        pass



    def __iter__(self):
        for key in self.entries:
            yield key
        #return self.entries.values()

    def items(self):
        return self.entries.items()

    @lru_cache(128)
    def __getitem__(self, index):
        '''Return the specific MFT entry. In case of an empty MFT, it will return
        None'''
        search_for = index
        if search_for in self._empty_entries:
            raise ValueError
        if search_for in self._entries_child_parent:
            search_for = self._entries_child_parent[search_for]

        return self._read_full_entry(search_for)




        return self.entries[index]

    def __len__(self):
        return len(self.entries)

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

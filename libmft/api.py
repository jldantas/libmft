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
'''
import struct
import enum
import collections
import logging
import itertools

from libmft.util.functions import convert_filetime, apply_fixup_array, flatten
from libmft.flagsandtypes import MftSignature, AttrTypes, MftUsageFlags
from libmft.attrcontent import StandardInformation, FileName, IndexRoot, Data, \
    AttributeList, Bitmap, ObjectID, VolumeName, VolumeInformation, ReparsePoint, \
    EaInformation, LoggedToolStream
from libmft.headers import MFTHeader, ResidentAttrHeader, NonResidentAttrHeader,  \
    AttributeHeader, DataRuns
from libmft.exceptions import MFTEntryException, FixUpError

MOD_LOGGER = logging.getLogger(__name__)

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
**!!!!!
 * Use two queues passing buffers, once processing is done, buffer
 is inserted in another queue and the application waits for this queue
 to have buffer available

The managers shit:
    https://docs.python.org/3/library/multiprocessing.html?highlight=queue#multiprocessing-managers
    https://stackoverflow.com/questions/11196367/processing-single-file-from-multiple-processes-in-python
'''

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
        header = AttributeHeader(binary_view)
        content = None

        if not header.non_resident:
            offset = header.resident_header.content_offset
            length = header.resident_header.content_len

            if header.attr_type_id is AttrTypes.FILE_NAME and mft_config["load_file_name"]:
                content = FileName.create_from_binary(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.STANDARD_INFORMATION and mft_config["load_std_info"]:
                content = StandardInformation.create_from_binary(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.INDEX_ROOT and mft_config["load_idx_root"]:
                content = IndexRoot.create_from_binary(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.ATTRIBUTE_LIST and mft_config["load_attr_list"]:
                content = AttributeList.create_from_binary(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.DATA and mft_config["load_data"]:
                content = Data(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.OBJECT_ID and mft_config["load_oject_id"]:
                content = ObjectID.create_from_binary(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.BITMAP and mft_config["load_bitmap"]:
                content = Bitmap(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.EA_INFORMATION and mft_config["load_ea_info"]:
                content = EaInformation(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.LOGGED_TOOL_STREAM and mft_config["load_log_tool_str"]:
                content = LoggedToolStream(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.REPARSE_POINT and mft_config["load_reparse"]:
                content = ReparsePoint.create_from_binary(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.VOLUME_NAME and mft_config["load_vol_name"]:
                content = VolumeName.create_from_binary(binary_view[offset:offset+length])
            elif header.attr_type_id is AttrTypes.VOLUME_INFORMATION and mft_config["load_vol_info"]:
                content = VolumeInformation.create_from_binary(binary_view[offset:offset+length])
            else:
                #print(self.header.attr_type_id)
                #TODO log/error when we don't know how to treat an attribute
                pass

        return cls(header, content)

    def is_non_resident(self):
        '''Helper function to check if an attribute is resident or not. Returns
        True if it is resident, otherwise returns False'''
        return self.header.non_resident

    def __len__(self):
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
            header = MFTHeader(bin_view[:MFTHeader.get_header_size()])
            entry = cls(header, {})

            if header.mft_record != entry_number:
                MOD_LOGGER.warning(f"The MFT entry number doesn't match. {entry_number} != {self.header_mft_record}")
            if len(binary_data) != header.entry_alloc_len:
                MOD_LOGGER.error(f"Expected MFT size is different than entry size.")
                raise MFTEntryException("Expected MFT size is different than entry size.", entry_number)
            try:
                apply_fixup_array(bin_view, header.fx_offset, header.fx_count, header.entry_alloc_len)
            except FixUpError as e:
                e.update_entry_binary(binary_data)
                e.update_entry_number(entry_number)
                raise

            if mft_config["load_attributes"]:
                entry._load_attributes(mft_config, bin_view[header.first_attr_offset:])
            if mft_config["load_slack"]:
                entry.slack = bin_view[header.entry_len:].tobytes()
        else:
            MOD_LOGGER.debug(f"Entry {entry_number} is empty.")
        bin_view.release() #release the underlying buffer

        return entry

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
            self._add_attribute(attr)
            offset += len(attr)

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

        return(ads_names)

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

class MFT():
    '''This class represents a MFT file. It has a bunch of MFT entries
    that have been parsed
    '''
    mft_config = {"entry_size" : 0,
                  "load_attributes" : True,
                  "load_slack" : True,
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
        self.mft_config = mft_config if mft_config is not None else MFT.mft_config
        self.mft_entry_size = self.mft_config["entry_size"]
        self.entries = {}

        if not self.mft_entry_size:
            self.mft_entry_size = self._find_mft_size(file_pointer)
        file_size = self._get_file_size(file_pointer)
        if (file_size % self.mft_entry_size):
            #TODO error handling (file size not multiple of mft size)
            MOD_LOGGER.error("Unexpected file size. It is not multiple of the MFT entry size.")

        end = int(file_size / self.mft_entry_size)
        data_buffer = bytearray(self.mft_entry_size)
        temp_entries = []
        for i in range(0, end):
            file_pointer.readinto(data_buffer)
            entry = MFTEntry.create_from_binary(self.mft_config, data_buffer, i)

            if entry is not None:
                if not entry.header.base_record_ref:
                    self.entries[i] = entry
                else:
                    base_record_ref = entry.header.base_record_ref
                    if base_record_ref in self.entries: #if the parent entry has been loaded
                        if self._is_related(self.entries[base_record_ref], entry):
                            self.entries[base_record_ref].copy_attributes(entry)
                        else: #can happen when you have an orphan entry
                            self.entries[i] = entry
                    else: #if the parent entry has not been loaded, put the entry in a temporary container
                        temp_entries.append(entry)
        #process the temporary list and add it to the "model"
        for entry in temp_entries:
            base_record_ref = entry.header.base_record_ref
            if base_record_ref in self.entries: #if the parent entry has been loaded
                if self._is_related(self.entries[base_record_ref], entry):
                    self.entries[base_record_ref].copy_attributes(entry)
                else: #can happen when you have an orphan entry
                    self.entries[i] = entry

    def _is_related(self, parent_entry, child_entry):
        '''This function checks if a child entry is related to the parent entry.
        This is done by comparing the reference and sequence numbers.'''
        if parent_entry.header.mft_record == child_entry.header.base_record_ref and \
           parent_entry.header.seq_number == child_entry.header.base_record_seq:
            return True
        else:
            return False

    def get_full_path(self, entry_number):
        #TODO ADS
        index = entry_number
        names = []
        name, attr = "", None
        root_id = 5
        #parent = 0

        if self[entry_number] is None:
            return None

        while index != root_id:
            fn_attrs = self[index].get_attributes(AttrTypes.FILE_NAME)

            if fn_attrs is not None:
                name, attr = "", None
                for fn in fn_attrs:
                    if fn.content.name_len > len(name):
                        name = fn.content.name
                        attr = fn

                if not self[attr.content.parent_ref].header.usage_flags & MftUsageFlags.DIRECTORY:
                    print("PARENT IS NOT A DIRECTORY")
                    #TODO error handling
                if attr.content.parent_seq != self[attr.content.parent_ref].header.seq_number: #orphan file
                    names.append(name)
                    names.append("_ORPHAN_")
                    break
                index = attr.content.parent_ref
                names.append(name)
            else: #some files just don't have a file name attribute
                #TODO throw an exception?
                #TODO logging
                return ""

        return "\\".join(reversed(names))

    def __iter__(self):
        for key in self.entries:
            yield key
        #return self.entries.values()

    def __getitem__(self, index):
        '''Return the specific MFT entry. In case of an empty MFT, it will return
        None'''
        return self.entries[index]

    def __len__(self):
        return len(self.entries)

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

    def _get_file_size(self, file_object):
        file_object.seek(0, 2)
        file_size = file_object.tell()
        file_object.seek(0, 0)

        return file_size

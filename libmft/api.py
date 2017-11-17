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
from libmft.exceptions import MFTEntryException

MOD_LOGGER = logging.getLogger(__name__)

class Attribute():
    '''Represents an attribute, header and content. Independently the type of
    attribute'''
    def __init__(self, bin_view):
        self.header = AttributeHeader(bin_view)
        self.content = None #content will be available only if the attribute is resident

        if not self.header.non_resident:
            offset = self.header.resident_header.content_offset
            length = self.header.resident_header.content_len

            if self.header.attr_type_id is AttrTypes.FILE_NAME:
                self.content = FileName.create_from_binary(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.STANDARD_INFORMATION:
                self.content = StandardInformation.create_from_binary(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.INDEX_ROOT:
                self.content = IndexRoot.create_from_binary(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.ATTRIBUTE_LIST:
                self.content = AttributeList.create_from_binary(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.DATA:
                self.content = Data(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.OBJECT_ID:
                self.content = ObjectID.create_from_binary(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.BITMAP:
                self.content = Bitmap(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.EA_INFORMATION:
                self.content = EaInformation(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.LOGGED_TOOL_STREAM:
                self.content = LoggedToolStream(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.REPARSE_POINT:
                self.content = ReparsePoint.create_from_binary(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.VOLUME_NAME:
                self.content = VolumeName.create_from_binary(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.VOLUME_INFORMATION:
                self.content = VolumeInformation.create_from_binary(bin_view[offset:offset+length])
            else:
                #print(self.header.attr_type_id)
                #TODO log/error when we don't know how to treat an attribute
                pass

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
    '''Represent one MFT entry. Upon creation it loads the MFT headers and
    necessary attributes. If the entry has a slack space, it also becomes available.

    As one entry can spawn multiple entries in case of lack of space, this class
    also mantains a relation with other entries, that way, all the information
    can be parsed referencing the base entry.
    '''
    #TODO test carefully how to find the correct index entry, specially with NTFS versions < 3
    def __init__(self, header=None, attrs=None, slack=None):
        '''Expects a writeable array with support to memoryview. Normally
        this would be a bytearray type. Once it has that, it reads the MFT
        and the necessary attributes. This read exactly one entry. Also,
        just to make sure the MFT entry number.
        '''
        self.header, self.attrs, self.slack = header, attrs, slack

    @classmethod
    def create_from_binary(cls, mft_config, binary_data, entry_number):
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
            apply_fixup_array(bin_view, header.fx_offset, header.fx_count, header.entry_alloc_len)

            if mft_config["load_attributes"]:
                entry._load_attributes(bin_view[header.first_attr_offset:])
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

    def _load_attributes(self, attrs_view):
        '''This function receives a view that starts at the first attribute
        until the end of the entry
        '''
        offset = 0

        while (attrs_view[offset:offset+4] != b'\xff\xff\xff\xff'):
            #pass all the information to the attr, as we don't know how
            #much content the attribute has
            attr = Attribute(attrs_view[offset:])
            self._add_attribute(attr)
            offset += len(attr)





    def is_empty(self):
        if self.header is None and self.attrs is None:
            return True
        else:
            return False

    def get_attributes(self, attr_type):
        '''Returns a list with one or more attributes of type "attr_type", in
        case they exist, otherwise, returns None. The attr_type must be a AttrTypes enum.'''
        if attr_type in self.attrs:
            return self.attrs[attr_type]
        else:
            return None

    def find_related_records(self):
        #TODO Change function name
        '''Returns the related entries to this entry. This means three things:
        1) The entry itself is always returned (who is more related than the entry itself?)
        2) If the entry has a base_record, it is returned
        3) If the entry is a base entry and has an resident ATTRIBUTE_LIST, it
        will parse the appropriate values and return

        It does NOT matter if the entry is not in use.'''
        records = [self.header.mft_record]

        if not self.header.base_record_ref: #if we are dealing with a base record, it might have an attribute_list
            attr_list = self.get_attributes(AttrTypes.ATTRIBUTE_LIST)
            if attr_list is not None:
                #TODO confirm if this is true
                #we assume that there can be only one ATTRIBUTE_LIST per entry
                attr = attr_list[0]
                if not attr.is_non_resident():
                    records += [list_entry.file_ref for list_entry in attr.content if list_entry.attr_type is AttrTypes.FILE_NAME]
        else:
            records.append(self.header.base_record_ref)

        return records

    def is_deleted(self):
        if self.header.usage_flags & MftUsageFlags.IN_USE:
            return False
        else:
            return True

    # def get_file_size(self):
    #     #TODO this is not a good name. change it.
    #     #TODO get ADSs sizes as well
    #     if AttrTypes.DATA in self.attrs:
    #         ret = [(attr.header.attr_name, len(attr.content)) for attr in self.attrs[AttrTypes.DATA] if not (attr.header.attr_name is None and len(attr.content) == 0 and attr.content is None)]
    #         if not ret:
    #             ret = (None, 0)
    #     else:
    #         #TODO error handling? what is the best way to comunicate that directories have no size
    #         ret = (None, 0)
    #
    #     return ret

    def __repr__(self):
        'Return a nicely formatted representation string'
        #TODO print the slack?
        return self.__class__.__name__ + '(header={}, attrs={})'.format(
            self.header, self.attrs)

class MFT():
    '''This class represents a MFT file. It has a bunch of MFT entries
    that have been parsed
    '''
    mft_config = {"load_attributes" : True,
                  "load_slack" : True}

    def __init__(self, file_pointer, size=0, use_cores=1):
        '''The initialization process takes a file like object "file_pointer"
        and loads it in the internal structures. "use_cores" can be definied
        if multiple cores are to be used. The "size" argument is the size
        of the MFT entries. If not provided, the class will try to auto detect
        it.
        '''
        self.mft_entry_size = size
        self.entries = []
        #this is a dictiony of lists, where the key is the parent number and
        #the members of the list are the related entries
        self.related_entries_nr = {}

        data_buffer = 0
        temp_entry_n_attr_list_nr = set()

        if not self.mft_entry_size:
            self.mft_entry_size = self._find_mft_size(file_pointer)
        #TODO test and verify what happens with really big files? overflow?
        file_pointer.seek(0, 2)
        end = int(file_pointer.tell() / self.mft_entry_size)
        if (file_pointer.tell() % self.mft_entry_size):
            #TODO error handling (file size not multiple of mft size)
            print("FILE SIZE NOT MULITPLE OF MFT ENTRY SIZE, POSSIBLE PROBLEM")
        file_pointer.seek(0, 0)
        data_buffer = bytearray(self.mft_entry_size)
        for i in range(0, end):
            file_pointer.readinto(data_buffer)
            entry = MFTEntry.create_from_binary(MFT.mft_config, data_buffer, i)

            #if not entry.is_empty():
            if entry is not None:
                self.entries.append(entry)

                #we have a problem. If the entry has a non-resident ATTRIBUTE_LIST,
                #it is impossible to find the entries based on the base record.
                #as such, in those cases, we cheat. Create a structure that allows
                #this mapping
                attr_list = entry.get_attributes(AttrTypes.ATTRIBUTE_LIST)
                if attr_list is not None:
                    if len(attr_list) == 1 and attr_list[0].is_non_resident():
                        temp_entry_n_attr_list_nr.add(i)
                    elif len(attr_list) > 1:
                        #TODO error handling? is there a case of multiple attr lists?
                        pass
            else:
                self.entries.append(None)

        self._fix_related_attr_list_non_resident(temp_entry_n_attr_list_nr)


        # base = 0
        # non_base = 0
        # for i, entry in enumerate(self.entries):
        #     if entry is not None:
        #         if entry.header.base_record_ref:
        #             non_base += 1
        #         else:
        #             base += 1
        # print(f"base {base}, non-base {non_base}")
        #print(self.related_entries_nr)
        #print(self.related_entries_nr)

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

    def _is_related(self, parent_entry, child_entry):
        '''This function checks if a child entry is related to the parent entry.
        This is done by comparing the reference and sequence numbers.'''
        if parent_entry.header.mft_record == child_entry.header.base_record_ref and \
           parent_entry.header.seq_number == child_entry.header.base_record_seq:
            return True
        else:
            return False

    def _fix_related_attr_list_non_resident(self, temp_entry_n_attr_list_nr):
        '''This function is a cheat. When we have an entry that has an
        ATTRIBUTE_LIST as non-resident, it is impossible to find the relation
        between entries.
        To fix this problem, this function receives an iterable with all the entries
        that have a non-resident ATTRIBUTE_LIST and search the other entries
        checking for which ones have reference to the ones flagged.
        Once it has been found, it puts the information in the variable
        self.related_entries_nr.
        '''
        #TODO test if this works and/or is worth
        for i, entry in enumerate(self.entries):
            if entry is not None:
                base_record_ref = entry.header.base_record_ref
                if base_record_ref in temp_entry_n_attr_list_nr and self._is_related(self[base_record_ref], self[i]):
                    if base_record_ref not in self.related_entries_nr:
                        self.related_entries_nr[base_record_ref] = set()
                    self.related_entries_nr[base_record_ref].add(i)

    def _find_base_entry(self, entry_number):
        '''Find the base entry of an entry. NTFS allows only a relationship of
        one level. If we have something more is because we might have a deleted
        entry messing up.

        In case of the entry is a base entry, it will return the entry number That
        was provided
        '''
        entry = self[entry_number]

        if not entry.header.base_record_ref:
            return entry_number
        else:
            if self._is_related(self[entry.header.base_record_ref], entry):
                return entry.header.base_record_ref
            else: #if the entries are not related, we have an error, probably because of a deleted entry
                #TODO error handling
                pass


    def _get_related_entries(self, entry_number):
        #TODO test if entry referenced by entry_number is None?
        parent_entry_number = self._find_base_entry(entry_number)
        data = []

        if parent_entry_number in self.related_entries_nr:
            data.append(self.related_entries_nr[parent_entry_number])
        data += self[parent_entry_number].find_related_records()

        return data

    def get_full_path(self, entry_number):
        #TODO ADS
        curr_entry_number = entry_number
        names = []
        temp_name = ""
        temp_attr = None
        root_id = 5
        parent = 0

        if self[entry_number] is None:
            return None

        while parent != root_id:
            fn_attrs = []

            numbers = set(self._get_related_entries(curr_entry_number))
            fn_attrs = [self[n].get_attributes(AttrTypes.FILE_NAME) for n in numbers if self[n] is not None]

            if fn_attrs:
                for attr in itertools.chain.from_iterable(fn_attrs):
                    #print(attr)
                    if attr.content.name_len > len(temp_name):
                        temp_attr = attr
                        temp_name = attr.content.name

                #print(temp_attr)
                if temp_attr.content.parent_seq != self[temp_attr.content.parent_ref].header.seq_number: #orphan file
                    names.append(temp_name)
                    names.append("_ORPHAN_")
                    break
                    #TODO exception?

                parent = temp_attr.content.parent_ref
                #print(curr_entry_number, parent, temp_attr.content.parent_ref)
                curr_entry_number = parent
                names.append(temp_name)
                temp_name = ""
            else: #some files just don't have a file name attribute
                #TODO throw an exception?
                #TODO logging
                return ""

        return "\\".join(reversed(names))

    def __getitem__(self, index):
        '''Return the specific MFT entry. In case of an empty MFT, it will return
        None'''
        entry = self.entries[index]

        return entry

        # if entry is not None:
        #     return entry
        # else:
        #     raise Exception
        #     pass

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

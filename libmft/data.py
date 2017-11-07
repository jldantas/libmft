import struct
import enum
import collections
import logging

from libmft.util.functions import convert_filetime, apply_fixup_array
from libmft.attributes import AttrTypes, StandardInformation, FileInfoFlags, \
    FileName, IndexRoot, Data, AttributeList, DataRuns
from libmft.headers import MftSignature, MftUsageFlags, MFTHeader, \
    AttrFlags, ResidentAttrHeader, NonResidentAttrHeader, AttributeHeader
from libmft.exceptions import MFTEntryException

MOD_LOGGER = logging.getLogger(__name__)

class Attribute():
    '''Represents an attribute, header and content. Independently the type of
    attribute'''
    def __init__(self, bin_view):
        self.header = AttributeHeader(bin_view)
        self.content = None

        if not self.header.is_non_resident:
            offset = self.header.resident_header.content_offset
            length = self.header.resident_header.content_len

            if self.header.attr_type_id is AttrTypes.STANDARD_INFORMATION:
                self.content = StandardInformation(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.ATTRIBUTE_LIST:
                self.content = AttributeList(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.FILE_NAME:
                self.content = FileName(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.DATA:
                self.content = Data(bin_view[offset:offset+length])
            elif self.header.attr_type_id is AttrTypes.INDEX_ROOT:
                self.content = IndexRoot(bin_view[offset:offset+length])
            else:
                #TODO log/error when we don~t know how to treat an attribute
                pass
        else:
            self.content = DataRuns(bin_view[self.header.non_resident_header.rl_offset:])


        if self.header.attr_type_id is AttrTypes.ATTRIBUTE_LIST and self.header.is_non_resident:
            print(self)

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
    def __init__(self, bin_stream, entry_number):
        '''Expects a writeable array with support to memoryview. Normally
        this would be a bytearray type. Once it has that, it reads the MFT
        and the necessary attributes. This read exactly one entry. Also,
        just to make sure the MFT entry number.
        '''
        self.header = None
        self.attrs = {}
        self.slack = None
        #as one mft entry can be spread across multiple entries, we add the entries here
        #self._related_entries = []

        bin_view = memoryview(bin_stream)
        attrs_view = None

        #TODO better definition of an "empty" entry
        #TODO move this check to a upper layer?
        #TODO in case of a empty entry, what is the best way to proceed? None?
        if bin_stream[0:4] != b"\x00\x00\x00\x00": #test if the entry is empty
            self.header = MFTHeader(bin_view[:MFTHeader.get_header_size()])
            if self.header.mft_record != entry_number:
                #TODO mft_record is something that showed up only in XP, maybe it is better to overwrite here? Needs testing
                logging.warning(f"The MFT entry number doesn't match. {entry_number} != {self.header_mft_record}")
            if len(bin_stream) != self.header.entry_alloc_len:
                logging.error(f"Expected MFT size is different than entry size.")
                raise MFTEntryException("Expected MFT size is different than entry size.", entry_number)
            apply_fixup_array(bin_view, self.header.fx_offset,
                self.header.fx_count, self.header.entry_alloc_len)
            attrs_view = bin_view[self.header.first_attr_offset:]
            #TODO have a "attribute parser" and a dispatcher?
            self._load_attributes(attrs_view)
            self.slack = bin_view[self.header.entry_len:].tobytes()
        else:
            logging.debug(f"Entry {entry_number} is empty.")
            self.attrs = None
            self._related_entries = None

        bin_view.release() #release the underlying buffer

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

    def add_related_entry(self, entry):
        # for key in entry.attrs:
        #     for attr in entry.attrs[key]:
        #         self._add_attribute(attr)
        #     entry.attrs[key] = None
        self._related_entries.append(entry)


    def is_empty(self):
        if self.header is None and self.attrs is None:
            return True
        else:
            return False

    def get_stream_size(self, name):
        pass

    def get_ads(self, ads_name):
        pass

    def get_attributes(self, attr_type):
        # temp = [r_entry.attrs[attr_type] for r_entry in self._related_entries if attr_type in r_entry.attrs]
        # print(temp)
        if attr_type in self.attrs:
            return self.attrs[attr_type]
        else:
            return None

    def get_standard_info(self):
        '''This is a helper function that returns only the content of the
        STANDARD_INFORMATION attribute. This will return a StandardInformation
        instance'''
        attrs = self.get_attributes(AttrTypes.STANDARD_INFORMATION)

        if len(attrs) == 1:
            return attrs[0].content
        else:
            #TODO error handling, no entry should have more than one STD INFO header, we have a problem
            print("MULTIPLE STD INFO HEADERS. PROBLEM.")

    def is_deleted(self):
        if self.header.usage_flags is MftUsageFlags.NOT_USED:
            return True
        else:
            return False

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

    def __init__(self, file_pointer, size=0, use_cores=1):
        '''The initialization process takes a file like object "file_pointer"
        and loads it in the internal structures. "use_cores" can be definied
        if multiple cores are to be used. The "size" argument is the size
        of the MFT entries. If not provided, the class will try to auto detect
        it.
        '''
        self.mft_entry_size = size
        self.entries = []
        self.base_ref_control = {}

        data_buffer = 0
        temporary_entry_holder = []

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
            entry = MFTEntry(data_buffer, i)

            if not entry.is_empty():
                self.entries.append(entry)
            else:
                self.entries.append(None)

            # self.entries.append(entry)
            # if not entry.is_empty():
            #     if entry.header.base_record_ref:
            #         print(entry.header.base_record_ref)

            # if i == 171977 or i == 213989 or i == 274357:
            #     print(entry)

        #     if not entry.is_empty():
        #         if not entry.header.base_record_ref:
        #             self.entries.append(entry)
        #         else:
        #             self.base_ref_control[i] = entry.header.base_record_ref
        #             self.entries.append(None)
        #
        #             if i == 171977 or i == 213989:
        #                 print("ADDED AS TEMPORARY")
        #
        #             temporary_entry_holder.append(entry)
        #     else:
        #         self.entries.append(None)
        #
        # # print(temporary_entry_holder)
        # for entry in temporary_entry_holder:
        #     base_record_ref = entry.header.base_record_ref
        #     # print(entry.header.mft_record, base_record_ref)
        #     self.entries[base_record_ref].add_related_entry(entry)

        #         base_record_ref = entry.header.base_record_ref
        #         self.base_ref_control[i] = base_record_ref
        #             self.entries
        #
        #
        #             if base_record_ref < len(self.entries):
        #                 self.entries[base_record_ref].add_related_entry(entry)
        #                 #TODO this is not good practice, think about a way of storing
        #                 #the same type of elements on the array
        #                 self.entries.append(base_record_ref)
        #             else:
        #                 temporary_entry_holder.append(entry)
        #                 self.entries.append(base_record_ref)
        #     else: #this should keep the entry id in sync with the index of the list
        #         self.entries.append(None)
        #
        # for entry in temporary_entry_holder:
        #     base_record_ref = entry.header.base_record_ref
        #     self.entries[base_record_ref].add_related_entry(entry)

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

    # def get_entry(self, entry_number):
    #     entry = self.entries[entry_number]
    #
    #     if entry is not None:
    #         try:
    #             entry.header
    #         except ValueError:
    #             entry = self.entries[entry]
    #
    #     return entry

    def get_full_path(self, entry_number):
        entry = self[entry_number]
        names = []
        root_id = 5
        parent = 0

        if entry is None:
            #TODO better way of doing this? exception? empty string? None?
            #I'm leaving empty string for now, so it is consistent (alwayes return string)
            return ""

        while parent != root_id:
            attrs = entry.get_attributes(AttrTypes.FILE_NAME)
            if attrs is None: #some un-named attribute, fire an exception?
                #TODO exception or None?
                return None
            for attr in attrs:
                parent = attr.content.parent_ref
                names.append(attr.content.name)
                entry = self[parent]

        return "\\".join(reversed(names))

    def __getitem__(self, index):
        entry = self.entries[index]

        if entry is not None:
            try:
                entry.header
            except AttributeError:
                entry = self.entries[entry]

        return entry

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

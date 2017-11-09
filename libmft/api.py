import struct
import enum
import collections
import logging
import itertools

from libmft.util.functions import convert_filetime, apply_fixup_array, flatten
from libmft.flagsandtypes import MftSignature, AttrTypes, MftUsageFlags
from libmft.attrcontent import StandardInformation, FileName, IndexRoot, Data, \
    AttributeList
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
                #TODO log/error when we don't know how to treat an attribute
                pass
        else:
            self.content = None

    def is_non_resident(self):
        '''Helper function to check if an attribute is resident or not. Returns
        True if it is resident, otherwise returns False'''
        return self.header.is_non_resident

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
        '''Returns a list with one or more attributes of type "attr_type", in
        case they exist, otherwise, returns None. The attr_type must be a AttrTypes enum.'''
        if attr_type in self.attrs:
            return self.attrs[attr_type]
        else:
            return None

    def find_related_records(self, attr_type):
        #TODO Change function name
        #TODO change commentary
        '''Finds all the entries that have a specific attribute by interpreting the
        information in the ATTRIBUTE_LIST attribute. This assumes that the infomation
        is resident and available.'''

        if self.header.base_record_ref:
            #TODO is this true?
            raise MFTEntryException("Only parent entries have an attribute list", self.header.mft_record)

        attr_list = self.get_attributes(AttrTypes.ATTRIBUTE_LIST)
        if attr_list is not None:
            if len(attr_list) == 1:
                attr = attr_list[0]
                if not attr.header.is_non_resident:
                    return [attr_list_entry.file_ref for attr_list_entry in attr.content if attr_list_entry.attr_type is attr_type]
                else:
                    #TODO exception or return?
                    raise MFTEntryException("ATTRIBUTE_LIST is non-resident!", self.header.mft_record)
            else:
                #TODO is this true? Entries can have only 1 ATTRIBUTE_LIST?
                raise MFTEntryException("More than 1 ATTRIBUTE_LIST!", self.header.mft_record)
        else:
            return None
            #raise MFTEntryException("Only parent entries have an attribute list", self.header.mft_record)

    # def get_standard_info(self):
    #     '''This is a helper function that returns only the content of the
    #     STANDARD_INFORMATION attribute. This will return a StandardInformation
    #     instance'''
    #     attrs = self.get_attributes(AttrTypes.STANDARD_INFORMATION)
    #
    #     if len(attrs) == 1:
    #         return attrs[0].content
    #     else:
    #         #TODO error handling, no entry should have more than one STD INFO header, we have a problem
    #         print("MULTIPLE STD INFO HEADERS. PROBLEM.")

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
        self.related_entries_nr = {}

        data_buffer = 0
        temp_entry_n_attr_list_nr = []

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
            #print(entry)

            if not entry.is_empty():
                self.entries.append(entry)

                # if entry.get_attributes(AttrTypes.ATTRIBUTE_LIST):
                #     temp = entry.get_attributes(AttrTypes.ATTRIBUTE_LIST)[0]
                #     #print(temp)
                #     if not temp.header.is_non_resident:
                #         for attr_list_e in temp.content:
                #             #print(attr_list_e)
                #             if attr_list_e.attr_type is AttrTypes.FILE_NAME and attr_list_e.file_ref != i:
                #                 print(entry)
                #                 print(entry.find_related_records(AttrTypes.FILE_NAME))
                #                 raise Exception("Debug")

                #we have a problem. If the entry has a non-resident ATTRIBUTE_LIST,
                #it is impossible to find the entries based on the base record.
                #as such, in those cases, we cheat. Create a structure that allows
                #this mapping
                attr_list = entry.get_attributes(AttrTypes.ATTRIBUTE_LIST)
                if attr_list is not None:
                    if len(attr_list) == 1 and attr_list[0].header.is_non_resident:
                        temp_entry_n_attr_list_nr.append(i)
                    elif len(attr_list) > 1:
                        #TODO error handling? is there a case of multiple attr lists?
                        pass
            else:
                self.entries.append(None)

        '''This logic is kind of strange. Once we find all the attributes
        that have non-resident ATTRIBUTE_LIST, we iterate over all the entries
        in search of those that have the parent as the ones mapped. Once we find
        the base is add to the dictonary of related entries. This should, in theory
        allow us to identify related entries.
        '''
        #TODO test if this works and/or is worth
        for i, entry in enumerate(self.entries):
            if entry is not None:
                base_record_ref = entry.header.base_record_ref
                if base_record_ref in temp_entry_n_attr_list_nr:
                    if base_record_ref not in self.related_entries_nr:
                        self.related_entries_nr[base_record_ref] = set()
                    self.related_entries_nr[base_record_ref].add(i)

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


    def _find_base_entry(self, entry_number):
        return_number = entry_number

        while self[return_number].header.base_record_ref:
            return_number = self[return_number].header.base_record_ref

        return return_number

    def _get_related_entries(self, entry_number, attr_type=None):
        #TODO test if entry referenced by entry_number is None?
        parent_entry_number = self._find_base_entry(entry_number)
        data = []

        if parent_entry_number in self.related_entries_nr:
            data.append(self.related_entries_nr[parent_entry_number])

        if attr_type is not None:
            entry = self[parent_entry_number]
            try:
                related_rec = entry.find_related_records(attr_type)
                if related_rec is not None:
                    data.append(related_rec)
            except MFTEntryException as e:
                MOD_LOGGER.exception("Data not found?")

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
            #TODO better way of doing this? exception? empty string? None?
            #I'm leaving empty string for now, so it is consistent (alwayes return string)
            return ""
        #entry = self._find_base_entry(entry_number)

        while parent != root_id:
            fn_entries = []

            numbers = self._get_related_entries(curr_entry_number, AttrTypes.FILE_NAME)
            numbers.append(curr_entry_number)
            #print(numbers)
            for number in flatten(numbers):
                entry  = self[number].get_attributes(AttrTypes.FILE_NAME)
                if entry is not None:
                    fn_entries.append(self[number].get_attributes(AttrTypes.FILE_NAME))

            if fn_entries:
                for attr in itertools.chain.from_iterable(fn_entries):
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

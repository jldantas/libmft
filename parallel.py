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

from libmft.util.functions import convert_filetime, apply_fixup_array, flatten, \
    get_file_size as _get_file_size
from libmft.flagsandtypes import MftSignature, AttrTypes, MftUsageFlags
from libmft.attrcontent import StandardInformation, FileName, IndexRoot, Data, \
    AttributeList, Bitmap, ObjectID, VolumeName, VolumeInformation, ReparsePoint, \
    EaInformation, LoggedToolStream
from libmft.headers import MFTHeader, ResidentAttrHeader, NonResidentAttrHeader,  \
    AttributeHeader, DataRuns
from libmft.exceptions import MFTEntryException, FixUpError

MOD_LOGGER = logging.getLogger(__name__)

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
            self.mft_entry_size = MFT._find_mft_size(file_pointer)
        file_size = _get_file_size(file_pointer)
        if (file_size % self.mft_entry_size):
            #TODO error handling (file size not multiple of mft size)
            MOD_LOGGER.error("Unexpected file size. It is not multiple of the MFT entry size.")

        end = int(file_size / self.mft_entry_size)
        data_buffer = bytearray(self.mft_entry_size)
        temp_entries = []
        for i in range(0, end):
            file_pointer.readinto(data_buffer)
            entry = MFTEntry.create_from_binary(self.mft_config, data_buffer, i)

            #some entries are marked as deleted and have no attributes, don't know why.
            #anyway, in this case, entry is considered invalid and not added
            if entry is not None and not entry.is_deleted() and entry.attrs:
                if not entry.header.base_record_ref:
                    self.entries[i] = entry
                else:
                    base_record_ref = entry.header.base_record_ref
                    if base_record_ref in self.entries: #if the parent entry has been loaded
                        if MFT._is_related(self.entries[base_record_ref], entry):
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

    @staticmethod
    def _is_related(parent_entry, child_entry):
        '''This function checks if a child entry is related to the parent entry.
        This is done by comparing the reference and sequence numbers.'''
        if parent_entry.header.mft_record == child_entry.header.base_record_ref and \
           parent_entry.header.seq_number == child_entry.header.base_record_seq:
            return True
        else:
            return False

    @classmethod
    def load_mp(cls, file_pointer, _mft_config=None):
        '''The initialization process takes a file like object "file_pointer"
        and loads it in the internal structures. "use_cores" can be definied
        if multiple cores are to be used. The "size" argument is the size
        of the MFT entries. If not provided, the class will try to auto detect
        it.
        '''
        import multiprocessing
        import queue

        mft_config = _mft_config if _mft_config is not None else MFT.mft_config
        mft_entry_size = mft_config["entry_size"]
        #self.entries = {}

        if not mft_entry_size:
            mft_entry_size = MFT._find_mft_size(file_pointer)
        file_size = _get_file_size(file_pointer)
        if (file_size % mft_entry_size):
            #TODO error handling (file size not multiple of mft size)
            MOD_LOGGER.error("Unexpected file size. It is not multiple of the MFT entry size.")

        end = int(file_size / mft_entry_size)

        #setup the multiprocessing stuff
        queue_size = 10
        n_processes = 3
        manager = multiprocessing.Manager()
        buffer_queue_in = manager.Queue(queue_size)
        buffer_queue_out = manager.Queue(queue_size)
        entries = manager.dict()
        temp_entries = manager.list()
        processes = [multiprocessing.Process(target=MFT._load_entry, args=(mft_config, buffer_queue_in, buffer_queue_out, entries, temp_entries)) for i in range(n_processes)]
        for p in processes:
            p.start()
        for i in range(queue_size):
            buffer_queue_out.put(bytearray(mft_entry_size))
        #start the game
        for i in range(0, end):
            try:
                data_buffer = buffer_queue_out.get(timeout=1)
                file_pointer.readinto(data_buffer)
                buffer_queue_in.put((i, data_buffer))
                #print("adding", i)
            except queue.Empty as e:
                print("DAMN")
                raise

        for i in range(queue_size):
            buffer_queue_in.put((-1, None))
        for p in processes:
            p.join()
        print("LOADING DONE")

        #process the temporary list and add it to the "model"
        for entry in temp_entries:
            base_record_ref = entry.header.base_record_ref
            if base_record_ref in entries: #if the parent entry has been loaded
                if MFT._is_related(entries[base_record_ref], entry):
                    entries[base_record_ref].copy_attributes(entry)
                else: #can happen when you have an orphan entry
                    entries[i] = entry


    @staticmethod
    def _load_entry(mft_config, input_queue, output_queue, entries, temp_entries):
        while True:
            i, data_buffer = input_queue.get()
            if data_buffer is not None:
                entry = MFTEntry.create_from_binary(mft_config, data_buffer, i)
                #some entries are marked as deleted and have no attributes, don't know why.
                #anyway, in this case, entry is considered invalid and not added
                if entry is not None and not entry.is_deleted() and entry.attrs:
                    if not entry.header.base_record_ref:
                        entries[i] = entry
                    else:
                        base_record_ref = entry.header.base_record_ref
                        if base_record_ref in entries: #if the parent entry has been loaded
                            if MFT._is_related(entries[base_record_ref], entry):
                                entries[base_record_ref].copy_attributes(entry)
                            else: #can happen when you have an orphan entry
                                entries[i] = entry
                        else: #if the parent entry has not been loaded, put the entry in a temporary container
                            temp_entries.append(entry)
                output_queue.put(data_buffer)
                #print("processed", i)
            else:
                break





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

                if attr.content.parent_seq != self[attr.content.parent_ref].header.seq_number: #orphan file
                    names.append(name)
                    names.append("_ORPHAN_")
                    break
                if not self[attr.content.parent_ref].header.usage_flags & MftUsageFlags.DIRECTORY:
                    print("PARENT IS NOT A DIRECTORY")
                    #TODO error handling
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

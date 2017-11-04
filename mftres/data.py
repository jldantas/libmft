import struct
#from datetime import datetime as _datetime, timedelta as _timedelta
import enum
import collections

from util.functions import convert_filetime, apply_fixup_array
from mftres.attributes import AttrTypes, StandardInformation, FileInfoFlags, \
    FileName, IndexRoot, Data, AttributeList
from mftres.headers import MftSignature, MftUsageFlags, MFTHeader, \
    AttrFlags, ResidentAttrHeader, NonResidentAttrHeader, AttributeHeader

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
        if self.header.attr_type_id is AttrTypes.ATTRIBUTE_LIST:
            if not self.header.is_non_resident:
                self.content = AttributeList(bin_view[offset:offset+length])
            else:
                self.content = AttributeList(None) #this case is much more a placeholer
                #TODO maybe just putting None is better?
        elif self.header.attr_type_id is AttrTypes.FILE_NAME:
            self.content = FileName(bin_view[offset:offset+length])
        elif self.header.attr_type_id is AttrTypes.DATA:
            if not self.header.is_non_resident:
                self.content = Data.create_from_resident(bin_view[offset:offset+length])
            else:
                self.content = Data.create_from_nonresident(self.header.non_resident_header)
        elif self.header.attr_type_id is AttrTypes.INDEX_ROOT:
            self.content = IndexRoot(bin_view[offset:offset+length])
        else:
            #TODO log/error when we don~t know how to treat an attribute
            pass

    def __len__(self):
        return len(self.header)

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(header={}, content={})'.format(
            self.header, self.content)

class MFTEntry():
    '''Represent one MFT entry. This loads the necessary MFT headers, the
    attributes and the MFT slack.
    '''
    #TODO test carefully how to find the correct index entry, specially with NTFS versions < 3
    def __init__(self, bin_stream, entry_number):
        '''Expects a writeable array with support to memoryview. Normally
        this would be a bytearray type. Once it has that, it reads the MFT
        and the necessary attributes. This read exactly one entry. Also,
        just to make sure the MFT entry number.
        '''
        self.mft_header = None
        self.attrs = {}
        self.slack = None

        bin_view = memoryview(bin_stream)
        attrs_view = None

        if bin_stream[0:4] != b"\x00\x00\x00\x00": #test if the entry is empty
            self.mft_header = MFTHeader(bin_view[:MFTHeader.size()])
            if self.mft_header.mft_record != entry_number:
                #TODO mft_record is something that showed up only in XP, maybe it is better to overwrite here? Needs testing
                print("SOMETHING IS WRONG, SONNY. RECORD NUMBER DOESN'T MATCH")

            if len(bin_stream) != self.mft_header.mft_alloc_size:
                #TODO error handling
                print("EXPECTED MFT SIZE IS DIFFERENT THAN ENTRY SIZE. PROBLEM!")
            apply_fixup_array(bin_view, self.mft_header.fx_offset,
                self.mft_header.fx_count, self.mft_header.mft_alloc_size)
            attrs_view = bin_view[self.mft_header.first_attr_offset:]
            #TODO have a "attribute parser" and a dispatcher?
            self._load_attributes(attrs_view)
            self.slack = bin_view[self.mft_header.mft_size:].tobytes()
        else:
            #TODO logging of the empty entry
            #TODO error handling
            self.attrs = None

        bin_view.release() #release the underlying buffer

    def _load_attributes(self, attrs_view):
        '''This function receives a view that starts at the first attribute
        until the end of the entry
        '''
        base_size = AttributeHeader.size()
        offset = 0

        while (attrs_view[offset:offset+4] != b'\xff\xff\xff\xff'):
            #pass all the information to the attr, as we don't know how
            #much content the attribute has
            attr = Attribute(attrs_view[offset:])
            offset += len(attr)
            if attr.header.attr_type_id not in self.attrs:
                self.attrs[attr.header.attr_type_id] = []
            self.attrs[attr.header.attr_type_id].append(attr)

    def is_empty(self):
        if self.mft_header is None and self.attrs is None:
            return True
        else:
            return False

    def get_stream_size(self, name):
        pass

    def get_ads(self, ads_name):
        pass

    def get_file_size(self):
        #TODO this is not a good name. change it.
        #TODO get ADSs sizes as well
        if AttrTypes.DATA in self.attrs:
            return [(attr.header.attr_name, attr.content.size) for attr in self.attrs[AttrTypes.DATA]]
        else:
            #TODO error handling? what is the best way to comunicate that directories have no size
            return 0
            pass


    def __repr__(self):
        'Return a nicely formatted representation string'
        #TODO print the slack?
        return self.__class__.__name__ + '(mft_header={}, attrs={})'.format(
            self.mft_header, self.attrs)

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
            entry = MFTEntry(data_buffer, i)
            if not entry.is_empty():
                #print(entry)
                # if i == 109056:
                if i == 115975:
                    print(entry)
                    #break
                if entry.mft_header.base_record_ref == 115975:
                    print(entry)
                    #if not entry.attrs[AttrTypes.DATA][0].header.non_resident_header.start_vcn:
                    #    print("FOUND DAMMIT")

                # if AttrTypes.ATTRIBUTE_LIST in entry.attrs:
                #     if entry.attrs[AttrTypes.ATTRIBUTE_LIST][0].content is not None:
                #         b = [a for a in entry.attrs[AttrTypes.ATTRIBUTE_LIST][0].content if a.attr_type is AttrTypes.DATA]
                #         if len(b) > 1:
                #             print(entry.attrs[AttrTypes.ATTRIBUTE_LIST][0].content)
                                #break

                # if AttrTypes.DATA in entry.attrs:
                #     if entry.attrs[AttrTypes.DATA][0].header.nonresident_flag is AttrNonResident.YES:
                #         if entry.attrs[AttrTypes.DATA][0].header.non_resident_header.start_vcn:
                #             print(entry)
                            #break

                # if AttrTypes.FILE_NAME in entry.attrs:
                #     print(entry.attrs[AttrTypes.FILE_NAME][0].content.name)
                    # if entry.attrs[AttrTypes.FILE_NAME][0].content.name == "folder1":
                    #     print(entry)
                    # if entry.attrs[AttrTypes.FILE_NAME][0].content.name == "folder2":
                    #     print(entry.attrs[AttrTypes.FILE_NAME])
                    # if entry.attrs[AttrTypes.FILE_NAME][0].content.name == "filelevel1.txt":
                    #     print(entry.get_file_size())
                    #     print(entry.attrs[AttrTypes.DATA])
                    # pass
                #print(entry)
                #print(entry.mft_header.mft_record)
                #print(i, [(key, len(value)) for key, value in entry.attrs.items()])
                #break
                pass
            #if i > 1:
            #    break
        #print(file_pointer.tell())

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
         to have buffer enabled

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

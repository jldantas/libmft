# -*- coding: utf-8 -*-
'''
-Definition of the API
This module is reponsible for the main parts that are exposed to the calling application.

- Structure of the API

The MFT has a number of different entries of type MFTEntry, these entries
have a header (MFTHeader) and a 'n' number of attributes and the attributes
have a header and a content. A rough of diagram can be seen below:

Diagram::

    +-----+
    | MFT |
    +--+--+
       |    +----------+
       +----+ MFTEntry |       +-----------+
       |    +----------+  +----+ MFTHeader |
       |                  |    +-----------+       +-----------------+
       |    +----------+  |                    +---+ AttributeHeader |
       +----+ MFTEntry +--+    +------------+  |   +-----------------+
       |    +----------+  +----+ Attributes +--+
       |         X        |    +------------+  |   +---------+
       |                  |          X         +---+ Content |
       |         X        |                        +---------+
       |                  |          X
       |         X        |
       |                  |          X
       |         X        |    +------------+
       |                  +----+ Attributes |
       |         X        |    +------------+
       |                  |
       |         X        |    +------------+
       |                  +----+ Datastream |
       |         X        |    +------------+
       |                  |          X
       |         X        |
       |                  |          X
       |         X        |
       |                  |          X
       |         X        |    +------------+
       |    +----------+  +----+ Datastream |
       +----+ MFTEntry |       +------------+
            +----------+

Each entity is:

* MFT - Represents the MFT
* MFTEntry - Represents one entry from the logical perspective, i.e., even if
    the attributes are spread across multiple entry in the file, they will be
    organized under the base entry
* MFTHeader - Represents the header of the MFT entry
* Attribute - Represents one attribute
* AttributeHeader - Represents the header of the attribute, including if it is
    resident or non-resident
* The content depends on the type of attribute

- Considerations

While a entry provides a logical MFT entry, a logical MFT entry may contain
multiple logical entries (hard links and data streams) which means that one entry
needs to be correctly processed to show all the data

.. moduleauthor:: Júlio Dantas <jldantas@gmail.com>
'''
import struct
import logging

from collections import defaultdict as _defaultdict
from functools import lru_cache
from operator import itemgetter as _itemgetter

from libmft.util.functions import convert_filetime, apply_fixup_array, flatten, \
    get_file_size as _get_file_size, get_file_reference
from libmft.flagsandtypes import MftSignature, AttrTypes, MftUsageFlags
from libmft.attribute import StandardInformation, FileName, IndexRoot, Data, \
    AttributeList, Bitmap, ObjectID, VolumeName, VolumeInformation, ReparsePoint, \
    EaInformation, LoggedToolStream, SecurityDescriptor, Ea
from libmft.attribute import ResidentAttrHeader, NonResidentAttrHeader, get_attr_info as _get_attr_info
from libmft.exceptions import FixUpError, DataStreamError, EntryError, MFTError, HeaderError

_MOD_LOGGER = logging.getLogger(__name__)


class MFTConfig():
    '''Configures how the libary behaves.

    The MFT is vast! There are plenty of details that may or may not be relevant
    to a particular application. Based on this, this class allows for some
    configurations to be passed to the library, modifying  what and how it is
    interpreted. That it is possible to configure the library to be as fast as
    possible.

    Warning:
        The option of parsing the MFT from an image has not been implemented!

    Attributes:
        entry_size (int): Size of a MFT entry. If it is zero the library will
            try to auto detect the size. Should be left alone unless you are
            sure of the size. Default is ``0``.
        apply_fixup_array (bool): Enable or disable the patching of the fix
            up array. If you are reading MFT from a memory dump, this should
            be set to ``False``. Default is ``True``.
        ignore_signature_check (bool): Enable or disable MFT entry signature check.
            This option controls if the 'FILE' or 'BAAD' signature will be checked.
            If this is disabled, the library will not parse this information.
        create_initial_information (bool): If you are reading a dumped MFT file,
            this should be ``True``. This allows the library to do a pre-parsing
            of the MFT and find the relationship between the entries. It should
            be ``False`` in case of having the whole disk image.
        load_dataruns (bool): Enables or disables the parsing of dataruns. If
            you don't have the disk image, loading the dataruns  is pretty useless
            and quite computationally intensive and should be disabled.
        load_std_info (bool): Enables or disables the parsing of the
            STANDARD_INFORMATION attribute.
        load_attr_list (bool): Enables or disables the parsing of the
            ATTRIBUTE_LIST attribute.
        load_file_name (bool): Enables or disables the parsing of the
            FILE_NAME attribute.
        load_object_id (bool): Enables or disables the parsing of the
            OBJECT_ID attribute.
        load_sec_desc (bool): Enables or disables the parsing of the
            SECURITY_DESCRIPTOR attribute.
        load_vol_name (bool): Enables or disables the parsing of the
            VOLUME_NAME attribute.
        load_vol_info (bool): Enables or disables the parsing of the
            VOLUME_INFORMATION attribute.
        load_idx_root (bool): Enables or disables the parsing of the
            INDEX_ROOT attribute.
        load_idx_alloc (bool): Enables or disables the parsing of the
            INDEX_ALLOCATION attribute.
        load_bitmap (bool): Enables or disables the parsing of the
            BITMAP attribute.
        load_reparse (bool): Enables or disables the parsing of the
            REPARSE_POINT attribute.
        load_ea_info (bool): Enables or disables the parsing of the
            EA_INFORMATION attribute.
        load_ea (bool): Enables or disables the parsing of the
            EA attribute.
        load_log_tool_str (bool): Enables or disables the parsing of the
            LOGGED_TOOL_STREAM attribute.
        load_datastream (bool): Enables or disables the parsing of the
            DATA attribute.
    '''

    def __init__(self):
        self._load_attrs = set()
        self.entry_size = 0
        self.apply_fixup_array = True
        self.ignore_signature_check = True
        self.create_initial_information = True
        self.load_dataruns = True

        # the "load attributes" is actually a set object with the entries
        # this allows quick comparison to check if we should parse an attribute
        # or not. 
        for attr_type in AttrTypes:
            self._load_attrs.add(attr_type)

    def _get_load_attr(self, attr_type):
            return attr_type in self._load_attrs

    def _set_load_attr(self, attr_type, case):
        if case:
            self._load_attrs.add(attr_type)
        else:
            if attr_type in self._load_attrs:
                self._load_attrs.remove(attr_type)

    load_std_info = property(lambda a: AttrTypes.STANDARD_INFORMATION in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.STANDARD_INFORMATION, x))
    load_attr_list = property(lambda a: AttrTypes.ATTRIBUTE_LIST in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.ATTRIBUTE_LIST, x))
    load_file_name = property(lambda a: AttrTypes.FILE_NAME in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.FILE_NAME, x))
    load_object_id = property(lambda a: AttrTypes.OBJECT_ID in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.OBJECT_ID, x))
    load_sec_desc = property(lambda a: AttrTypes.SECURITY_DESCRIPTOR in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.SECURITY_DESCRIPTOR, x))
    load_vol_name = property(lambda a: AttrTypes.VOLUME_NAME in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.VOLUME_NAME, x))
    load_vol_info = property(lambda a: AttrTypes.VOLUME_INFORMATION in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.VOLUME_INFORMATION, x))
    load_idx_root = property(lambda a: AttrTypes.INDEX_ROOT in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.INDEX_ROOT, x))
    load_idx_alloc = property(lambda a: AttrTypes.INDEX_ALLOCATION in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.INDEX_ALLOCATION, x))
    load_bitmap = property(lambda a: AttrTypes.BITMAP in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.BITMAP, x))
    load_reparse = property(lambda a: AttrTypes.REPARSE_POINT in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.REPARSE_POINT, x))
    load_ea_info = property(lambda a: AttrTypes.EA_INFORMATION in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.EA_INFORMATION, x))
    load_ea = property(lambda a: AttrTypes.EA in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.EA, x))
    load_log_tool_str = property(lambda a: AttrTypes.LOGGED_TOOL_STREAM in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.LOGGED_TOOL_STREAM, x))
    load_datastream = property(lambda a: AttrTypes.DATA in a._load_attrs, lambda a, x : a._set_load_attr(AttrTypes.DATA, x))

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

    __slots__ = ("baad", "fx_offset", "fx_count", "lsn", "seq_number",
        "hard_link_count", "first_attr_offset", "usage_flags",
        "_entry_len", "entry_alloc_len",
        "base_record_ref", "base_record_seq", "next_attr_id",
        "mft_record")

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
        self.baad, self.fx_offset, self.fx_count, self.lsn, self.seq_number, \
        self.hard_link_count, self.first_attr_offset, self.usage_flags, \
        self._entry_len, self.entry_alloc_len, \
        self.base_record_ref, self.base_record_seq, self.next_attr_id, \
        self.mft_record = header

    @classmethod
    def get_static_content_size(cls):
        '''Return the header size'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, mft_config, binary_view):
        '''Creates a new object MFTHeader from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of the attribute

        Returns:
            MFTHeader: New object using hte binary stream as source
        '''
        sig, fx_offset, fx_count, lsn, seq_number, hard_link_count, first_attr_offset, \
        usage_flags, entry_len, alloc_len, base_record, next_attr_id, record_n = \
            cls._REPR.unpack(binary_view[:cls._REPR.size])

        baad = None
        if not mft_config.ignore_signature_check:
            if sig == b"FILE":
                baad = False
            elif sig == b"BAAD":
                baad = True
            else:
                raise HeaderError("Entry has no valid signature.", "MFTHeader")

        if fx_offset < MFTHeader._REPR.size: #header[1] is fx_offset
            raise HeaderError("Fix up array begins within the header.", "MFTHeader")
        if first_attr_offset < cls._REPR.size: #first attribute offset < header size
            raise HeaderError("First attribute offset points to inside of the header.", "MFTHeader")
        if entry_len > alloc_len: #entry_len > entry_alloc_len
            raise HeaderError("Logical size of the MFT is bigger than MFT allocated size.", "MFTHeader")

        file_ref, file_seq = get_file_reference(base_record)
        nw_obj = cls((baad, fx_offset, fx_count, lsn, seq_number, hard_link_count,
            first_attr_offset, MftUsageFlags(usage_flags), entry_len, alloc_len,
            file_ref, file_seq, next_attr_id, record_n))

        return nw_obj

    def __len__(self):
        '''Returns the logical size of the mft entry'''
        return self._entry_len

    def __repr__(self):
        'Return a nicely formatted representation string'
        return (f'{self.__class__.__name__}(is_baad={str(self.baad)},'
                f'fx_offset={self.fx_offset},fx_count={self.fx_count},'
                f'lsn={self.lsn},seq_number={self.seq_number},'
                f'hard_link_count={self.hard_link_count},'
                f'first_attr_offset={self.first_attr_offset},'
                f'usage_flags={str(self.usage_flags)},entry_len={self._entry_len},'
                f'entry_alloc_len={self.entry_alloc_len},base_record_ref={self.base_record_ref},'
                f'base_record_seq={self.base_record_seq},next_attr_id={self.next_attr_id}, mft_record={self.mft_record})'
                )

class Datastream():
    '''Represents one datastream for an entry.

    This class has all the necessary information to represent a NTFS datastream.
    Because it is possible to have multiple DATA attributes spread or not across different
    entries and resident data as well, trying to interpret everything directly from
    the entry gets messy and not uniform.

    The Datastream class exists to try to solve these problems. With it we can
    access a datastream, independently of the type, in a uniform wayself.

    Args:
        name (str): The name of the datastream

    Attributes:
        name (str): Datastream's name
        size (int): Logical size, in bytes, of a datastream, effectively speaking,
            this is the size of the file
        alloc_size (int): Allocated size, in bytes, on the disk. This is supposed
            to be different from ``size`` in case of a sparse file
        cluster_count (int): Number of clusters allocated for the datastream
    '''
    def __init__(self, name=None):
        '''Initialize on datastream. The only parameter accepted is the
        name of the datastream.'''
        #we don't need to save the compression usize because we are unable to access the rest of the disk
        #TODO confirm this (^) affirmation
        self.name = name
        self.size = 0 #logical size
        self.alloc_size = 0 #allocated size
        self.cluster_count = 0
        self._data_runs = None #data runs only exist if the attribute is non resident
        #the _data_runs variable stores a tuple with the format:
        #(start_vcn, dataruns). We use the start_vcn to sort the dataruns in
        #the correct order
        self._content = None
        self._data_runs_sorted = False

    def _get_content(self):
        '''Returns the content of a resident datastream'''
        if not self.is_resident():
            raise DataStreamError("Non resident datastream don't have content")

        return self._content

    def _is_resident(self):
        '''Check is the datastream is resident or non resident. In case of it
        begin resident, it is possible to recover the content of the datastream
        '''
        if self._data_runs is None:
            return True
        else:
            return False

    def _get_dataruns(self):
        '''Returns a list of dataruns, in order.
        '''
        if self._data_runs is None:
            raise DataStreamError("Resident datastream don't have dataruns")

        if not self._data_runs_sorted:
            self._data_runs.sort(key=_itemgetter(0))
            self._data_runs_sorted = True

        return [data[1] for data in self._data_runs]

    content = property(_get_content, doc="The content of a resident datastream")
    is_resident = property(_is_resident, doc="True if the datastream is resident, False otherwise")
    dataruns = property(_get_dataruns, doc="Dataruns associated with a datastream")

    def add_data_attribute(self, data_attr):
        '''Interprets a DATA attribute and add it to the datastream.'''
        if data_attr.header.attr_type_id is not AttrTypes.DATA:
            raise DataStreamError("Invalid attribute. A Datastream deals only with DATA attributes")
        if data_attr.header.attr_name != self.name:
            raise DataStreamError(f"Data from a different stream '{data_attr.header.attr_name}' cannot be add to this stream")

        if data_attr.header.non_resident:
            nonr_header = data_attr.header
            if self._data_runs is None:
                self._data_runs = []
            if nonr_header.end_vcn > self.cluster_count:
                self.cluster_count = nonr_header.end_vcn
            if not nonr_header.start_vcn: #start_vcn == 0
                self.size = nonr_header.curr_sstream
                self.alloc_size = nonr_header.alloc_sstream
            self._data_runs.append((nonr_header.start_vcn, nonr_header.data_runs))
            self._data_runs_sorted = False
        else: #if it is resident
            self.size = self.alloc_size = data_attr.header.content_len
            self._pending_processing = None
            #respects mft_config["load_data"]
            self._content = data_attr.content.content

    def add_from_datastream(self, source_ds):
        '''Add information from another datastream. Verifies if the datastream
        added is correct and copy the relevant fields if necessary.'''
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

    def __iadd__(self, other):
        if isinstance(other, Data):
            self.add_data_attribute(other)
        elif isinstance(other, Datastream):
            self.add_from_datastream(other)
        else:
            raise NotImplemented

        return self

    def __len__(self):
        return self.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return f'{self.__class__.__name__}(name={self.name}, size={self.size}, alloc_size={self.alloc_size}, cluster_count={self.cluster_count}, _data_runs={self._data_runs}, _content={self._content}, _data_runs_sorted={self._data_runs_sorted})'

class Attribute():
    '''Represents an attribute, header and content. Independently the type of
    attribute'''
    _dispatcher = {AttrTypes.STANDARD_INFORMATION : StandardInformation.create_from_binary,
                   AttrTypes.ATTRIBUTE_LIST : AttributeList.create_from_binary,
                   AttrTypes.FILE_NAME : FileName.create_from_binary,
                   AttrTypes.OBJECT_ID : ObjectID.create_from_binary,
                   AttrTypes.SECURITY_DESCRIPTOR : SecurityDescriptor.create_from_binary,
                   AttrTypes.VOLUME_NAME : VolumeName.create_from_binary,
                   AttrTypes.VOLUME_INFORMATION : VolumeInformation.create_from_binary,
                   AttrTypes.DATA : Data.create_from_binary,
                   AttrTypes.INDEX_ROOT : IndexRoot.create_from_binary,
                   AttrTypes.INDEX_ALLOCATION : FileName.create_from_binary,
                   AttrTypes.BITMAP : Bitmap.create_from_binary,
                   AttrTypes.REPARSE_POINT : ReparsePoint.create_from_binary,
                   AttrTypes.EA_INFORMATION : EaInformation.create_from_binary,
                   AttrTypes.EA : Ea.create_from_binary,
                   AttrTypes.LOGGED_TOOL_STREAM : LoggedToolStream,
    }


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
    def create_from_binary(cls, non_resident, load_dataruns, binary_view):
        if not non_resident:
            header = ResidentAttrHeader.create_from_binary(binary_view)
            content = cls._dispatcher[header.attr_type_id](binary_view[header.content_offset:header.content_offset+header.content_len])
        else:
            header = NonResidentAttrHeader.create_from_binary(load_dataruns, binary_view)
            content = None

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
        return f'{self.__class__.__name__}(header={self.header}, content={self.content})'

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
        self.header, self.attrs, self.data_streams = header, attrs, []

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
        try:
            header = MFTHeader.create_from_binary(mft_config, bin_view[:MFTHeader.get_static_content_size()])
        except HeaderError as e:
            e.update_entry_number(entry_number)
            e.update_entry_binary(binary_data)
            raise
        entry = cls(header, {})

        if header.mft_record != entry_number:
            _MOD_LOGGER.warning("The MFT entry number doesn't match. %d != %d", entry_number, header.mft_record)
        if len(binary_data) != header.entry_alloc_len:
            _MOD_LOGGER.error("Expected MFT size is different than entry size.")
            raise EntryError(f"Expected MFT size ({len(binary_data)}) is different than entry size ({header.entry_alloc_len}).", binary_data, entry_number)
        if mft_config.apply_fixup_array:
            apply_fixup_array(bin_view, header.fx_offset, header.fx_count, header.entry_alloc_len)

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
        load_attrs = mft_config._load_attrs
        #get_basic_attr_header_info = AttributeHeader.get_basic_attr_header_info

        while (attrs_view[offset:offset+4] != b'\xff\xff\xff\xff'):
            #pass all the information to the attr, as we don't know how
            #much content the attribute has
            #try:

            attr_type, attr_len, non_resident = _get_attr_info(attrs_view[offset:])
            if attr_type in load_attrs:
                attr = Attribute.create_from_binary(non_resident, mft_config.load_dataruns, attrs_view[offset:])
                if not attr.header.attr_type_id is AttrTypes.DATA:
                    self._add_attribute(attr)
                else:
                    self._add_datastream(attr)
            offset += attr_len


            # except EntryError as e:
            #     e.update_entry_number(entry_number)
            #     e.update_entry_binary(binary_data)


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

    def get_datastream(self, name=None):
        '''Returns the size of the data or an ads. The ads has to be the name of the file'''
        return self._find_datastream(name)

    def get_datastream_names(self):
        '''Returns a set with the datastream names. If there is no datastream,
        returns None
        '''
        ads_names = set()

        for stream in self.data_streams:
            ads_names.add(stream.name)

        if len(ads_names):
            return ads_names
        else:
            return None

    def get_main_filename_attr(self):
        '''Returns the main filename attribute of the entry. This is found
        searching for the lowest attribute id, once that has been found, it loops
        again over the filenames attributes searching other attributes that represent
        the same name and return the best one possible based on the type of the
        name (name_type)

        '''
        fn_attrs = self.get_attributes(AttrTypes.FILE_NAME)
        high_attr_id = 0xFFFFFFFF
        main_fn = None

        if fn_attrs is not None:
            for fn_attr in fn_attrs:
                if fn_attr.header.attr_id < high_attr_id:
                    main_fn = fn_attr
                    high_attr_id = fn_attr.header.attr_id

            #TODO is this necessary? Maybe the first name is always the with with the biggest namespace
            for fn_attr in fn_attrs:
                if main_fn.content.parent_ref == fn_attr.content.parent_ref and \
                    main_fn.content.parent_seq == fn_attr.content.parent_seq and \
                    fn_attr.content.name_type.value < main_fn.content.name_type.value:
                        main_fn = fn_attr

        return main_fn

    def get_unique_filename_attrs(self):
        fn_attrs = self.get_attributes(AttrTypes.FILE_NAME)
        control = None
        result = None

        if fn_attrs is not None:
            control = {}
            for fn in fn_attrs:
                temp = (fn.content.parent_ref, fn.content.parent_seq)
                if temp not in control:
                    control[temp] = fn
                else:
                    if fn.content.name_type.value < control[temp].content.name_type.value:
                        control[temp] = fn
            result = [fn for fn in control.values()]

        return result

    def is_deleted(self):
        '''Returns True if an entry is marked as deleted, otherwise, returns False.'''
        if self.header.usage_flags & MftUsageFlags.IN_USE:
            return False
        else:
            return True

    def is_directory(self):
        '''Returns True is the entry is a directory, otherwise, returns False.'''
        if self.header.usage_flags & MftUsageFlags.DIRECTORY:
            return True
        else:
            return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        #TODO print the slack?
        return self.__class__.__name__ + '(header={}, attrs={}, data_stream={})'.format(
            self.header, self.attrs, self.data_streams)



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
            _MOD_LOGGER.debug("Entry %d is empty.", record_n)

        return nw_obj

    @classmethod
    def get_static_content_size(cls):
        '''Returns the static size of the content never taking in consideration
        variable fields, for example, names.

        Returns:
            int: The size of the content, in bytes
        '''
        return cls._REPR.size

    #TODO change this to receive the numbers instead of entry, so the api is "normalized"?
    def is_related(self, child_entry):
        '''Compares if two entries are related, based on the reference and sequence
        numbers.

        Args:
            child_entry (_MFTEntryStub) - Entry to compare if the it is child or not

        Returns:
            (bool): True if the entries are related, False otherwise'''
        if self.mft_record == child_entry.base_record_ref and \
           self.seq_number == child_entry.base_record_seq:
            return True
        else:
            return False


    def __repr__(self):
        'Return a nicely formatted representation string'
        #TODO print the slack?
        return self.__class__.__name__ + '(mft_record={}, seq_number={}, base_record_ref={}, base_record_seq={})'.format(
            self.mft_record, self.seq_number, self.base_record_ref, self.base_record_seq)




class MFT():
    '''This class represents a MFT file. It has a bunch of MFT entries
    that have been parsed
    '''

    def __init__(self, file_pointer, mft_config=MFTConfig()):
        #TODO redo documentation
        '''The initialization process takes a file like object "file_pointer"
        and loads it in the internal structures. "use_cores" can be definied
        if multiple cores are to be used. The "size" argument is the size
        of the MFT entries. If not provided, the class will try to auto detect
        it.
        '''
        self.file_pointer = file_pointer
        self.mft_config = mft_config
        self.mft_entry_size = self.mft_config.entry_size
        self._entries_parent_child = _defaultdict(list) #holds the relation ship between parent and child
        self._entries_child_parent = {} #holds the relation between child and parent
        self._empty_entries = set() #holds the empty entries
        self._number_valid_entries = 0

        if not self.mft_entry_size: #if entry size is zero, try to autodetect
            _MOD_LOGGER.info("Trying to detect MFT size entry")
            self.mft_entry_size = MFT._find_mft_size(file_pointer)

        if self.mft_config.create_initial_information:
            self._load_stub_info()

    def copy_from_loaded_mft(other_mft):
        #TODO do we need this?
        import copy
        self._entries_parent_child = copy.deepcopy(other_mft._entries_parent_child)
        self._entries_child_parent = copy.deepcopy(other_mft._entries_child_parent)
        self._empty_entries = copy.deepcopy(other_mft._empty_entries)
        self._number_valid_entries = other_mft._number_valid_entries

    def get_entry_full_path(self, entry_number=None, entry=None):
        if entry_number is None and entry is None:
            raise MFTError("Provide entry_number or entry parameters")
        if entry_number is not None and entry is not None:
            raise MFTError("Can't provide both entry_number and entry")

        if entry_number:
            working_entry = self[entry_number]
        elif entry:
            working_entry = entry
        else:
            raise MFTError("Something went very wrong when parsing the function arguments.")

        fn_attr = working_entry.get_main_filename_attr()
        if fn_attr is None:
            raise EntryError("No FILENAME attribute available, can't calculate path", b"", working_entry.header.mft_record)

        names = [fn_attr.content.name]
        root_id = 5
        index, seq = fn_attr.content.parent_ref, fn_attr.content.parent_seq
        is_orphan = False

        while index != root_id:
            try:
                parent_entry = self[index]

                if seq != parent_entry.header.seq_number:
                    is_orphan = True
                    break
                else:
                    parent_fn_attr = parent_entry.get_main_filename_attr()
                    index, seq = parent_fn_attr.content.parent_ref, parent_fn_attr.content.parent_seq
                    names.append(parent_fn_attr.content.name)
            except ValueError as e:
                is_orphan = True
                break

        return (is_orphan, "\\".join(reversed(names)))

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
        _MOD_LOGGER.info("Loading basic info from file...")
        for i in range(0, _get_file_size(self.file_pointer), mft_entry_size):
            mft_record_n = int(i/mft_entry_size)    #calculate which is the entry number
            self.file_pointer.seek(i)
            self.file_pointer.readinto(data_buffer)
            stub = _MFTEntryStub.load_from_file_pointer(data_buffer, mft_record_n)
            temp.append(stub)
        #from the information loaded, find which entries are related and the one that are empty
        _MOD_LOGGER.info("Mapping related entries...")
        for i, stub in enumerate(temp):
            if stub is not None:
                self._number_valid_entries += 1
                if stub.base_record_ref and temp[stub.base_record_ref].is_related(stub): #stub.base_record_ref is not 0
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
            entry.merge_entries(temp_entry)

        return entry

    def __iter__(self):
        returned = 0

        for i in range(0, _get_file_size(self.file_pointer), self.mft_entry_size):
            mft_record_n = int(i/self.mft_entry_size)
            if returned > self._number_valid_entries:
                #TODO customize this exception
                raise MFTError("Something is wrong...")
            if mft_record_n in self._empty_entries or mft_record_n in self._entries_child_parent:
                continue
            else:
                returned += 1
                yield self[mft_record_n]


    @lru_cache(512)
    def __getitem__(self, index):
        '''Return the specific MFT entry. In case of an empty MFT, it will return
        None'''
        if index in self._empty_entries:
            raise ValueError(f"Entry {index} is empty.")
        if index in self._entries_child_parent:
            raise ValueError(f"Entry {index} is a child entry.")

        return self._read_full_entry(index)

    def __len__(self):
        return self._number_valid_entries

    @staticmethod
    def _find_mft_size(file_object):
        sizes = [1024, 4096, 512, 2048, 256, 8192, 1]
        sigs = [member.value for name, member in MftSignature.__members__.items()]

        first_sig = file_object.read(4)
        second_sig = None
        if first_sig not in sigs:
            raise MFTError("Entry signature not found.")
        for size in sizes:
            file_object.seek(size, 0)
            second_sig = file_object.read(4)
            if second_sig in sigs:
                _MOD_LOGGER.info("MFT entry size found = %d", size)
                break
        file_object.seek(0)

        if size == 1:
            raise MFTError("Could not find MFT entry size. Please provide one manually.")

        return size

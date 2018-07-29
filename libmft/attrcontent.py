# -*- coding: utf-8 -*-
'''
This module contains all the known information about attributes. In particular,
their content. By definition, as we have only the $MFT available for processing
we can't have any of the content in case of non-resident attributes.
That means that all the classes below EXPECT the attribute to be resident.

Calling the constructors for a non-resident attribute MAY lead to an unxpected
behaviour.
'''
import struct
import logging
from itertools import chain as _chain
from operator import getitem as _getitem
from uuid import UUID
from abc import ABCMeta, abstractmethod
from math import ceil as _ceil

from libmft.util.functions import convert_filetime, get_file_reference
from libmft.flagsandtypes import AttrTypes, NameType, FileInfoFlags, \
    IndexEntryFlags, VolumeFlags, ReparseType, ReparseFlags, CollationRule, \
    SecurityDescriptorFlags, ACEType, ACEControlFlags, ACEAccessFlags
from libmft.exceptions import ContentError

_MOD_LOGGER = logging.getLogger(__name__)

#TODO verify, in general, if it is not better to encode the data within the
#attributes as tuple or list and use properties to access by name

#TODO rewrite the commentaries


#******************************************************************************
# ABSTRACT CLASS FOR ATTRIBUTE CONTENT
#******************************************************************************
class AttributeContentBase(metaclass=ABCMeta):
    '''Base class for attributes.'''
    @classmethod
    @abstractmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        pass

    @abstractmethod
    def __len__(self):
        '''Get the actual size of the content, as some attributes have variable sizes'''
        pass

    @abstractmethod
    def __eq__(self, other):
        pass

class AttributeContentNoRepr(AttributeContentBase):
    pass

class AttributeContentRepr(AttributeContentBase):
    '''Most, if not all attributes have a representation in binary, this forces
    a particular interface when using them'''
    @classmethod
    @abstractmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        pass

#******************************************************************************
# TIMESTAMPS class
#******************************************************************************
class Timestamps(AttributeContentRepr):
    _REPR = struct.Struct("<4Q")

    def __init__(self, content=(None,)*4):
        '''Represents a timestamp and uses exactly a 4-element tuple

        Args:
            content (iterable), where:
                [0] (datetime) - created time
                [1] (datetime) - changed time
                [2] (datetime) - mft change time
                [3] (datetime) - accessed
        '''
        self.created, self.changed, self.mft_changed, self.accessed = content

    def astimezone(self, timezone):
        if self.created.tzinfo is timezone:
            return self
        else:
            nw_obj = cls((None,)*4)
            nw_obj.created = self.created.astimezone(timezone)
            nw_obj.changed = self.changed.astimezone(timezone)
            nw_obj.mft_changed = self.mft_changed.astimezone(timezone)
            nw_obj.accessed = self.accessed.astimezone(timezone)

            return nw_obj

    @classmethod
    def get_representation_size(cls):
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Creates a new object Timestamps from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of the attribute

        Returns:
            Timestamps: New object using hte binary stream as source
        '''
        repr = cls._REPR

        if len(binary_stream) != repr.size:
            raise ContentError("Invalid binary stream size")

        _MOD_LOGGER.debug("Unpacking TIMESTAMPS content")
        content = repr.unpack(binary_stream)
        nw_obj = cls()
        nw_obj.created, nw_obj.changed, nw_obj.mft_changed, nw_obj.accessed = \
            convert_filetime(content[0]), convert_filetime(content[1]), \
            convert_filetime(content[2]), convert_filetime(content[3])
        _MOD_LOGGER.debug(f"Timestamp created: {nw_obj}")
        _MOD_LOGGER.debug("TIMESTAMPS object created successfully")

        return nw_obj

    def __eq__(self, other):
        if isinstance(other, Timestamps):
            return self.created == other.created and self.changed == other.changed \
                and self.mft_changed == other.mft_changed and self.accessed == other.accessed
        return False

    def __len__(self):
        return Timestamps._REPR.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(created={self.created}, changed={self.changed}, mft_changed={self.mft_changed}, accessed={self.accessed})'

#******************************************************************************
# STANDARD_INFORMATION ATTRIBUTE
#******************************************************************************
class StandardInformation(AttributeContentRepr):
    '''Represents the STANDARD_INFORMATION converting the timestamps to
    datetimes and the flags to FileInfoFlags representation.'''
    _TIMESTAMP_SIZE = Timestamps.get_representation_size() #TODO looks ugly... fix
    _REPR = struct.Struct("<4I2I2Q")
    _REPR_NO_NFTS_3_EXTENSION = struct.Struct("<4I")
    '''
        TIMESTAMPS(32)
            Creation time - 8
            File altered time - 8
            MFT/Metadata altered time - 8
            Accessed time - 8
        Flags - 4 (FileInfoFlags)
        Maximum number of versions - 4
        Version number - 4
        Class id - 4
        Owner id - 4 (NTFS 3+)
        Security id - 4 (NTFS 3+)
        Quota charged - 8 (NTFS 3+)
        Update Sequence Number (USN) - 8 (NTFS 3+)
    '''

    def __init__(self, content=(None,)*8):
        '''Creates a StandardInformation object. The content has to be an iterable
        with precisely 0 elements in order.
        If content is not provided, a 0 element tuple, where all elements are
        None, is the default argument

        Args:
            content (iterable), where:
                [0] (Timestamps) - Timestamp object with the correct timestamps
                [1] (FileInfoFlags) - flags
                [2] (int) - maximum number of versions
                [3] (int) - version number
                [4] (int) - Owner id
                [5] (int) - Security id
                [6] (int) - Quota charged
                [7] (int) - Update Sequence Number
        '''
        self.timestamps, self.flags, self.max_n_versions, self.version_number, \
        self.class_id, self.owner_id,  \
        self.security_id, self.quota_charged, self.usn = content

    @classmethod
    def get_representation_size(cls):
        '''Returns the static size of the content never taking in consideration
        variable fields, for example, names.

        Returns:
            int: The size of the content, in bytes
        '''
        return cls._TIMESTAMP_SIZE + cls._REPR.size


    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Creates a new object StandardInformation from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of the attribute

        Returns:
            StandardInformation: New object using hte binary stream as source
        '''
        _MOD_LOGGER.debug("Unpacking STANDARD_INFORMATION content")

        timestamps = Timestamps.create_from_binary(binary_stream[:cls._TIMESTAMP_SIZE])
        if len(binary_stream) == cls._TIMESTAMP_SIZE + cls._REPR.size:
            _MOD_LOGGER.debug("Unpacking STDInfo with NTFS 3 extension")
            main_content = cls._REPR.unpack(binary_stream[cls._TIMESTAMP_SIZE:])
            nw_obj = cls(_chain((timestamps,), main_content))
        else:
            _MOD_LOGGER.debug("Unpacking STDInfo without NTFS 3 extension")
            main_content = cls._REPR_NO_NFTS_3_EXTENSION.unpack(binary_stream[cls._TIMESTAMP_SIZE:])
            nw_obj = cls(_chain((timestamps,), main_content, (None, None, None, None)))
        nw_obj.flags = FileInfoFlags(nw_obj.flags)
        _MOD_LOGGER.debug("StandardInformation object created successfully")

        return nw_obj

    def __eq__(self, other):
        if isinstance(other, StandardInformation):
            return self.timestamps == other.timestamps and self.flags == other.flags \
                and self.max_n_versions == other.max_n_versions and self.version_number == other.version_number \
                and self.class_id == other.class_id and self.owner_id == other.owner_id \
                and self.security_id == other.security_id and self.quota_charged == other.quota_charged \
                and self.usn == other.usn
        return False

    def __len__(self):
        return StandardInformation._TIMESTAMP_SIZE + StandardInformation._REPR.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + (f'(timestamps={repr(self.timestamps)},'
            f'flags={str(self.flags)}, max_n_versions={self.max_n_versions},'
            f'version_number={self.version_number}, class_id={self.class_id},'
            f'owner_id={self.owner_id}, security_id={self.security_id},'
            f'quota_charged={self.quota_charged}, usn={self.usn})')

#******************************************************************************
# ATTRIBUTE_LIST ATTRIBUTE
#******************************************************************************
class AttributeListEntry(AttributeContentRepr):
    '''This class holds one entry on the attribute list attribute.'''
    _REPR = struct.Struct("<IH2B2QH")
    '''
        Attribute type - 4
        Length of a particular entry - 2
        Length of the name - 1 (in characters)
        Offset to name - 1
        Starting VCN - 8
        File reference - 8
        Attribute ID - 1
        Name (unicode) - variable
    '''

    def __init__(self, content=(None,)*9):
        '''Creates an AttributeListEntry object. The content has to be an iterable
        with precisely 9 elements in order.
        If content is not provided, a tuple filled with 'None' is the default
        argument.

        Args:
            content (iterable), where:
                [0] (AttrTypes) - Attribute type
                [1] (int) - length of the entry
                [2] (int) - length of the name
                [3] (int) - offset to the name
                [4] (int) - start vcn
                [5] (int) - file reference number
                [6] (int) - file sequence number
                [7] (int) - attribute id
                [8] (str) - name
        '''
        self.attr_type, self._entry_len, _, self.name_offset, \
        self.start_vcn, self.file_ref, self.file_seq, self.attr_id, self.name = content

    def _get_name_length(self):
        '''Returns the length of the name based on the name'''
        if self.name is None:
            return 0
        else:
            return len(self.name)

    @classmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object AttributeListEntry from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of the attribute

        Returns:
            AttributeListEntry: New object using hte binary stream as source
        '''
        _MOD_LOGGER.debug("Unpacking ATTRIBUTE_LIST content")
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])
        nw_obj = cls()

        if content[2]:
            name = binary_view[content[3]:content[3]+(2*content[2])].tobytes().decode("utf_16_le")
        else:
            name = None
        file_ref, file_seq = get_file_reference(content[5])
        nw_obj.attr_type, nw_obj._entry_len, nw_obj.name_offset, nw_obj.start_vcn,  \
        nw_obj.file_ref, nw_obj.file_seq, nw_obj.attr_id, nw_obj.name = \
        AttrTypes(content[0]), content[1], content[3], content[4], \
        file_ref, file_seq, content[6], name
        _MOD_LOGGER.debug("AttributeListEntry object created successfully")

        return nw_obj

    #the name length can derived from the name, so, we don't need to keep in memory
    name_len = property(_get_name_length, doc='Length of the name')

    def __len__(self):
        '''Returns the size of the entry, in bytes'''
        return self._entry_len

    def __eq__(self, other):
        if isinstance(other, AttributeListEntry):
            return self.attr_type == other.attr_type and self.entry_len == other.entry_len \
                and self.name_len == other.name_len and self.name_offset == other.name_offset \
                and self.start_vcn == other.start_vcn and self.file_ref == other.file_ref \
                and self.file_seq == other.file_seq and self.attr_id == other.attr_id \
                and self.name == other.name
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(attr_type={self.attr_type}, entry_len={self._entry_len}, name_len={self.name_len}, name_offset={self.name_offset}, start_vcn={self.start_vcn}, file_ref={self.file_ref}, file_seq={self.file_seq}, attr_id={self.attr_id}, name={self.name})'

class AttributeList(AttributeContentNoRepr):
    '''Represents the ATTRIBUTE_LIST attribute, holding all the entries, if available,
    as AttributeListEntry objects.'''

    def __init__(self, content=[]):
        '''Creates an AttributeList content representation. Content has to be a
        list of AttributeListEntry that will be referred by the object. To create
        from a binary string, use the function 'create_from_binary' '''
        self.attr_list = content

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object AttributeList from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray. As the AttributeList is a contatiner, the binary stream has
        to have multiple AttributeListEntry encoded.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of multiple AttributeListEntry

        Returns:
            AttributeList: New object using the binary stream as source
        '''
        attr_list = []
        offset = 0

        while True:
            _MOD_LOGGER.debug("Creating AttributeListEntry object from binary stream...")
            entry = AttributeListEntry.create_from_binary(binary_view[offset:])
            offset += len(entry)
            attr_list.append(entry)
            if offset >= len(binary_view):
                break
            _MOD_LOGGER.debug(f"Next AttributeListEntry offset = {offset}")
        _MOD_LOGGER.debug("AttributeListEntry object created successfully")

        return cls(attr_list)

    def __len__(self):
        '''Return the number of entries in the attribute list'''
        return len(self.attr_list)

    def __iter__(self):
        '''Return the iterator for the representation of the list, so it is
        easier to check everything'''
        return iter(self.attr_list)

    def __getitem__(self, index):
        '''Return the AttributeListEntry at the specified position'''
        return _getitem(self.attr_list, index)

    def __eq__(self, other):
        if isinstance(other, AttributeList):
            return self.attr_list == other.attr_list
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(attr_list={self.attr_list})'

#******************************************************************************
# OBJECT_ID ATTRIBUTE
#******************************************************************************
class ObjectID(AttributeContentNoRepr):
    '''This class represents an Object ID.'''

    def __init__(self,  content=(None,)*4):
        '''Creates a StandardInformation object. The content has to be an iterable
        with precisely 4 elements in order.
        If content is not provided, a 4 element tuple, where all elements are
        None, is the default argument.

        Args:
            content (iterable), where:
                [0] (UID) - object id
                [1] (UID) - birth volume id
                [2] (UID) - virth object id
                [3] (UID) - birth domain id
        '''
        self.object_id, self.birth_vol_id, self.birth_object_id, \
        self.birth_domain_id = content
        self.__size = sum([16 for data in content if content is not None])

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object ObjectID from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of an ObjectID

        Returns:
            ObjectID: New object using the binary stream as source
        '''
        uid_size = 16

        #some entries might not have all four ids, this line forces
        #to always create 4 elements, so contruction is easier
        uids = [UUID(bytes_le=binary_view[i*uid_size:(i+1)*uid_size].tobytes()) if i * uid_size < len(binary_view) else None for i in range(0,4)]
        _MOD_LOGGER.debug("ObjectID object created successfully")

        return cls(uids)

    def __len__(self):
        '''Get the actual size of the content, as some attributes have variable sizes'''
        return self.__size

    def __eq__(self, other):
        if isinstance(other, ObjectID):
            return self.object_id == other.object_id and self.birth_vol_id == other.birth_vol_id \
                and self.birth_object_id == other.birth_object_id and self.birth_domain_id == other.birth_domain_id
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(object_id={self.object_id}, birth_vol_id={self.birth_vol_id}, birth_object_id={self.birth_object_id}, birth_domain_id={self.birth_domain_id})'

#******************************************************************************
# VOLUME_NAME ATTRIBUTE
#******************************************************************************
class VolumeName(AttributeContentNoRepr):
    '''This class represents a VolumeName attribute.'''
    def __init__(self, name):
        '''Initialize a VolumeName object, receives the name of the volume:

        Args:
            name (str) - name of the volume
        '''
        self.name = name

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object VolumeName from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of an VolumeName

        Returns:
            VolumeName: New object using the binary stream as source
        '''
        name = binary_view.tobytes().decode("utf_16_le")
        _MOD_LOGGER.debug("ObjectID object created successfully")

        return cls(name)

    def __len__(self):
        '''Returns the length of the name'''
        return len(self.name)

    def __eq__(self, other):
        if isinstance(other, VolumeName):
            return self.name == other.name
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(name={self.name})'

#******************************************************************************
# VOLUME_INFORMATION ATTRIBUTE
#******************************************************************************
class VolumeInformation(AttributeContentRepr):
    '''This class represents a VolumeInformation attribute.'''

    _REPR = struct.Struct("<8x2BH")
    ''' Unknow - 8
        Major version number - 1
        Minor version number - 1
        Volume flags - 2
    '''

    def __init__(self, content=(None,)*3):
        '''Creates a VolumeInformation object. The content has to be an iterable
        with precisely 3 elements in order.
        If content is not provided, a 3 element tuple, where all elements are
        None, is the default argument

        Args:
            content (iterable), where:
                [0] (int) - major version
                [1] (int) - minor version
                [2] (VolumeFlags) - Volume flags
        '''
        self.major_ver, self.minor_ver, self.vol_flags = content

    @classmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object VolumeInformation from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of an VolumeInformation

        Returns:
            VolumeInformation: New object using the binary stream as source
        '''
        content = cls._REPR.unpack(binary_view)

        nw_obj = cls(content)
        nw_obj.vol_flags = VolumeFlags(content[2])
        _MOD_LOGGER.debug("VolumeInformation object created successfully")

        return nw_obj

    def __len__(self):
        '''Returns the length of the attribute'''
        return cls._REPR.size

    def __eq__(self, other):
        if isinstance(other, VolumeInformation):
            return self.major_ver == other.major_ver and self.minor_ver == other.minor_ver \
                    and self.vol_flags == other.vol_flags
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(major_ver={self.major_ver}, minor_ver={self.minor_ver}, vol_flags={self.vol_flags})'

#******************************************************************************
# FILENAME ATTRIBUTE
#******************************************************************************
class FileName(AttributeContentRepr):
    '''Represents the FILE_NAME converting the timestamps to
    datetimes and the flags to FileInfoFlags representation.

    It is important to note that windows apparently does not update the fields
    "allocated size of file" and "real size of file". These should be calculated
    using the data attributes for correct informaiton.
    '''
    #_REPR = struct.Struct("<7Q2I2B")
    _TIMESTAMP_SIZE = Timestamps.get_representation_size() #TODO looks ugly... fix
    _REPR = struct.Struct("<1Q32x2Q2I2B")
    #_REPR = struct.Struct("<5Q16x2I2B")
    ''' File reference to parent directory - 8
        TIMESTAMPS(32)
            Creation time - 8
            File altered time - 8
            MFT/Metadata altered time - 8
            Accessed time - 8
        Allocated size of file - 8 (multiple of the cluster size)
        Real size of file - 8 (actual file size, might also be stored by the directory)
        Flags - 4
        Reparse value - 4
        Name length - 1 (in characters)
        Name type - 1
        Name - variable
    '''

    def __init__(self, content=(None, )*10):
        '''Creates a FileName object. The content has to be an iterable
        with precisely 11 elements in order.
        If content is not provided, a tuple filled with 'None' is the default
        argument.

        Args:
            content (iterable), where:
                [0] (int) - parent refence
                [1] (int) - parent sequence
                [2] (Timestamps) - timestampes
                [3] (int) - allocated file size
                [4] (int) - real file size
                [5] (FileInfoFlags) - flags
                [6] (int) - reparse value
                [7] (int) - name length
                [8] (NameType) - name type
                [9] (str) - name
        '''
        self.parent_ref, self.parent_seq, self.timestamps, self.alloc_file_size, \
        self.real_file_size, self.flags, self.reparse_value, _, self.name_type, \
        self.name = content

    def _get_name_len(self):
        return len(self.name)

    #the name length can derived from the name, so, we don't need to keep in memory
    name_len = property(_get_name_len, doc='Length of the name')

    @classmethod
    def get_representation_size(cls):
    #def get_static_content_size(cls):
        '''Returns the static size of the content never taking in consideration
        variable fields, for example, names.

        Returns:
            int: The size of the content, in bytes
        '''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object FileName from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of an FileName

        Returns:
            FileName: New object using the binary stream as source
        '''
        nw_obj = cls()
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])
        name = binary_view[cls._REPR.size:].tobytes().decode("utf_16_le")
        timestamps = Timestamps.create_from_binary(binary_view[8:8+cls._TIMESTAMP_SIZE])
        file_ref, file_seq = get_file_reference(content[0])

        nw_obj.parent_ref, nw_obj.parent_seq, nw_obj.timestamps, nw_obj.alloc_file_size, \
        nw_obj.real_file_size, nw_obj.flags, nw_obj.reparse_value, nw_obj.name_type, \
        nw_obj.name = \
        file_ref, file_seq, timestamps, content[1], content[2], FileInfoFlags(content[3]),  \
        content[4], NameType(content[6]), name

        return nw_obj

    def __eq__(self, other):
        if isinstance(other, FileName):
            return self.parent_ref == other.parent_ref and self.parent_seq == other.parent_seq \
                and self.timestamps == other.timestamps and self.alloc_file_size == other.alloc_file_size \
                and self.real_file_size == other.real_file_size and self.flags == other.flags \
                and self.reparse_value == other.reparse_value and self.name_type == other.name_type \
                and self.name == other.name
        return False

    def __len__(self):
        return  FileName._REPR.size + name_len

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(parent_ref={}, parent_seq={}, timestamps={!s}, alloc_file_size={}, real_file_size={}, flags={!s}, reparse_value={}, name_len={}, name_type={!s}, name={})'.format(
            self.parent_ref, self.parent_seq, self.timestamps, self.alloc_file_size, self.real_file_size, self.flags,
            self.reparse_value, self.name_len, self.name_type, self.name)

#******************************************************************************
# DATA ATTRIBUTE
#******************************************************************************
class Data(AttributeContentNoRepr):
    '''This is a placeholder class to the data attribute. By itself, it does
    very little and holds almost no information. If the data is resident, holds the
    content and the size.
    '''
    def __init__(self, bin_view):
        '''Initialize the class. Expects the binary_view that represents the
        content. Size information is derived from the content.
        '''
        self.content = bin_view.tobytes()

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        return cls(binary_stream)

    def __len__(self):
        '''Returns the logical size of the file'''
        return len(self.content)

    def __eq__(self, other):
        if isinstance(other, Data):
            return self.content == other.content
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(content={self.content})'

#******************************************************************************
# INDEX_ROOT ATTRIBUTE
#******************************************************************************
class IndexNodeHeader(AttributeContentRepr):
    '''Represents the Index Node Header, that is always present in the INDEX_ROOT
    and INDEX_ALLOCATION attribute.'''

    _REPR = struct.Struct("<4I")
    ''' Offset to start of index entry - 4
        Offset to end of used portion of index entry - 4
        Offset to end of the allocated index entry - 4
        Flags - 4
    '''

    def __init__(self, content=(None,)*4):
        '''Creates a IndexNodeHeader object. The content has to be an iterable
        with precisely 4 elements in order.
        If content is not provided, a 4 element tuple, where all elements are
        None, is the default argument

        Args:
            content (iterable), where:
                [0] (int) - start offset
                [1] (int) - end offset
                [2] (int) - allocated size of the node
                [3] (int) - non-leaf node Flag (has subnodes)
        '''
        self.start_offset, self.end_offset, self.end_alloc_offset, \
        self.flags = content

    @classmethod
    def get_representation_size(cls):
        '''Returns the static size of the content never taking in consideration
        variable fields, for example, names.

        Returns:
            int: The size of the content, in bytes
        '''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object IndexNodeHeader from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of an IndexNodeHeader

        Returns:
            IndexNodeHeader: New object using the binary stream as source
        '''
        nw_obj = cls(cls._REPR.unpack(binary_view[:cls._REPR.size]))
        _MOD_LOGGER.debug("IndexNodeHeader object created successfully")

        return nw_obj

    def __len__(self):
        '''Get the actual size of the content, as some attributes have variable sizes'''
        return cls._REPR.size

    def __eq__(self, other):
        if isinstance(other, IndexNodeHeader):
            return self.start_offset == other.start_offset \
                and self.end_offset == other.end_offset \
                and self.end_alloc_offset == other.end_alloc_offset \
                and self.flags == other.flags
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(start_offset={self.start_offset}, end_offset={self.end_offset}, end_alloc_offset={self.end_alloc_offset}, flags={self.flags})'

class IndexEntry(AttributeContentRepr):
    '''Represents an entry in the index.'''

    _REPR = struct.Struct("<Q2HI")
    ''' Undefined - 8
        Length of entry - 2
        Length of content - 2
        Flags - 4
        Content - variable
        VCN of child node - 8 (exists only if flag is set, aligned to a 8 byte boundary)
    '''
    _REPR_VCN = struct.Struct("<Q")

    def __init__(self, content=(None,)*6):
        '''Creates a StandardInformation object. The content has to be an iterable
        with precisely 0 elements in order.
        If content is not provided, a 0 element tuple, where all elements are
        None, is the default argument

        Args:
            content (iterable), where:
                [0] (int) - file reference?
                [1] (int) - length of the entry
                [2] (int) - length of the content
                [3] (int) - flags (1 = index has a sub-node, 2 = last index entry in the node)
                [4] (FileName or binary_string) - content
                [5] (int) - vcn child node
        '''
        #TODO don't save this here and overload later?
        #TODO confirm if this is really generic or is always a file reference
        #this generic variable changes depending what information is stored
        #in the index
        self.generic, self.entry_len, self.content_len, self.flags, \
        self.content, self.vcn_child_node = content

    @classmethod
    def get_representation_size(cls):
        '''Returns the static size of the content never taking in consideration
        variable fields, for example, names.

        Returns:
            int: The size of the content, in bytes
        '''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_view, content_type=None):
        '''Creates a new object IndexEntry from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of an IndexEntry
            content_type (AttrTypes) - Type of content present in the index

        Returns:
            IndexEntry: New object using the binary stream as source
        '''
        repr_size = cls._REPR.size
        content = cls._REPR.unpack(binary_view[:repr_size])
        nw_obj = cls()

        vcn_child_node = (None,)
        #if content is known (filename), create a new object to represent the content
        if content_type is AttrTypes.FILE_NAME and content[2]:
            binary_content = FileName.create_from_binary(binary_view[repr_size:repr_size+content[2]])
        else:
            binary_content = binary_view[repr_size:repr_size+content[2]].tobytes()
        #if there is a next entry, we need to pad it to a 8 byte boundary
        if content[3] & IndexEntryFlags.CHILD_NODE_EXISTS:
            temp_size = repr_size + content[2]
            boundary_fix = (content[1] - temp_size) % 8
            vcn_child_node = cls._REPR_VCN.unpack(binary_view[temp_size+boundary_fix:temp_size+boundary_fix+8])

        nw_obj.generic, nw_obj.entry_len, nw_obj.content_len, nw_obj.flags, \
        nw_obj.content, nw_obj.vcn_child_node = content[0], content[1], content[2], \
            IndexEntryFlags(content[3]), binary_content, vcn_child_node
        _MOD_LOGGER.debug("IndexEntry object created successfully")

        return nw_obj

    def __len__(self):
        '''Get the actual size of the content, as some attributes have variable sizes'''
        return self.entry_len

    def __eq__(self, other):
        if isinstance(other, IndexEntry):
            return self.generic == other.generic \
                and self.entry_len == other.entry_len \
                and self.content_len == other.content_len \
                and self.flags == other.flags and self.content == other.content \
                and self.vcn_child_node == other.vcn_child_node
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(generic={}, entry_len={}, content_len={}, flags={!s}, content={}, vcn_child_node={})'.format(
            self.generic, self.entry_len, self.content_len, self.flags,
            self.content, self.vcn_child_node)

class IndexRoot(AttributeContentRepr):
    '''Represents the INDEX_ROOT'''

    _REPR = struct.Struct("<3IB3x")
    ''' Attribute type - 4
        Collation rule - 4
        Bytes per index record - 4
        Clusters per index record - 1
        Padding - 3
    '''

    def __init__(self, content=(None,)*4, node_header=None, idx_entry_list=None):
        '''Creates a IndexRoot object. The content has to be an iterable
        with precisely 4 elements in order.
        If content is not provided, a 4 element tuple, where all elements are
        None, is the default argument

        Args:
            content (iterable), where:
                [0] (AttrTypes) - attribute type
                [1] (CollationRule) - collation rule
                [2] (int) - index record size in bytes
                [3] (int) - index record size in clusters
            node_header (IndexNodeHeader) - the node header related to this index root
            idx_entry_list (list of IndexEntry)- list of index entries that belong to
                this index root
        '''
        self.attr_type, self.collation_rule, self.index_len_in_bytes, \
        self.index_len_in_cluster = content
        self.node_header = node_header
        self.index_entry_list = idx_entry_list

    @classmethod
    def get_representation_size(cls):
        '''Returns the static size of the content never taking in consideration
        variable fields, for example, names.

        Returns:
            int: The size of the content, in bytes
        '''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object IndexRoot from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of an IndexRoot

        Returns:
            IndexRoot: New object using the binary stream as source
        '''
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])
        nw_obj = cls()
        nw_obj.node_header = IndexNodeHeader.create_from_binary(binary_view[cls._REPR.size:])
        index_entry_list = []
        attr_type = AttrTypes(content[0]) if content[0] else None

        offset = cls._REPR.size + nw_obj.node_header.start_offset
        #loads all index entries related to the root node
        while True:
            entry = IndexEntry.create_from_binary(binary_view[offset:], attr_type)
            index_entry_list.append(entry)
            if entry.flags & IndexEntryFlags.LAST_ENTRY:
                break
            else:
                offset += entry.entry_len

        nw_obj.index_entry_list = index_entry_list
        nw_obj.attr_type, nw_obj.collation_rule, nw_obj.index_len_in_bytes, \
        nw_obj.index_len_in_cluster = attr_type, CollationRule(content[1]), \
            content[2], content[3]

        return nw_obj

    def __len__(self):
        '''Get the actual size of the content, as some attributes have variable sizes'''
        return self.cls._REPR.size

    def __eq__(self, other):
        if isinstance(other, IndexRoot):
            return self.attr_type == other.attr_type \
                and self.collation_rule == other.collation_rule \
                and self.index_len_in_bytes == other.index_len_in_bytes \
                and self.index_len_in_cluster == other.index_len_in_cluster and self.node_header == other.node_header \
                and self.index_entry_list == other.index_entry_list
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(attr_type={!s}, collation_rule={}, index_len_in_bytes={}, index_len_in_cluster={}, node_header={}, index_entry_list={})'.format(
            self.attr_type, self.collation_rule, self.index_len_in_bytes,
            self.index_len_in_cluster, self.node_header, self.index_entry_list)

#******************************************************************************
# BITMAP ATTRIBUTE
#******************************************************************************
class Bitmap(AttributeContentNoRepr):
    '''Represents the bitmap attribute'''
    def __init__(self, bitmap_view):
        self._bitmap = bitmap_view.tobytes()

    def allocated_entries(self):
        '''Returs a generator that provides all the allocated entries
        for the bitmap'''
        for entry_number in range(len(self._bitmap) * 8):
            if self.entry_allocated(entry_number):
                yield entry_number

    def entry_allocated(self, entry_number):
        '''Check if an entry is allocated'''
        index, offset = divmod(entry_number, 8)
        return bool(self._bitmap[index] & (1 << offset))

    def get_next_empty(self):
        '''Returns the next empty entry'''
        #TODO probably not the best way, redo
        for i, byte in enumerate(self._bitmap):
            if byte != 255:
                for offset in range(8):
                    if not byte & (1 << offset):
                        return (i * 8) + offset

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        return cls(binary_stream)

    def __len__(self):
        '''Returns the size of the bitmap in bytes'''
        return len(self._bitmap)

    def __eq__(self, other):
        if isinstance(other, Bitmap):
            return self._bitmap == other._bitmap
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(bitmap={self._bitmap})'

#******************************************************************************
# REPARSE_POINT ATTRIBUTE
#******************************************************************************
class JunctionOrMount():
    _REPR = struct.Struct("<4H")
    ''' Offset to target name - 2 (relative to 16th byte)
        Length of target name - 2
        Offset to print name - 2 (relative to 16th byte)
        Length of print name - 2
    '''
    def __init__(self, target_name=None, print_name=None):
        self.target_name, self.print_name = target_name, print_name

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object JunctionOrMount from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of an JunctionOrMount

        Returns:
            JunctionOrMount: New object using the binary stream as source
        '''
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])
        repar_point_size = ReparsePoint.get_static_content_size()

        offset = repar_point_size + content[0]
        target_name = binary_view[offset:offset+content[1]].tobytes().decode("utf_16_le")
        offset = repar_point_size + content[2]
        print_name = binary_view[offset:offset+content[3]].tobytes().decode("utf_16_le")

        return cls(target_name, print_name)

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(target_name={}, print_name={})'.format(
            self.target_name, self.print_name)

class ReparsePoint():
    _REPR = struct.Struct("<IH2x")
    ''' Reparse type flags - 4
            Reparse tag - 4 bits
            Reserved - 12 bits
            Reparse type - 2
        Reparse data length - 2
        Padding - 2
    '''
    def __init__(self, content=(None,)*5):
        '''Creates a IndexRoot object. The content has to be an iterable
        with precisely 5 elements in order.
        If content is not provided, a 5 element tuple, where all elements are
        None, is the default argument

        Args:
            content (iterable), where:
                [0] (ReparseType) - Reparse point type
                [1] (ReparseFlags) - Reparse point flags
                [2] (int) - reparse data length
                [3] (binary str) - guid (exists only in 3rd party reparse points)
                [4] (variable) - content of the reparse type
        '''
        self.reparse_type, self.reparse_flags, self.data_len, \
        self.guid, self.data = content

    @classmethod
    def get_static_content_size(cls):
        '''Returns the static size of the content never taking in consideration
        variable fields, for example, names.

        Returns:
            int: The size of the content, in bytes
        '''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_view):
        '''Creates a new object JunctionOrMount from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            ReparsePoint (memoryview of bytearray) - A binary stream with the
                information of an JunctionOrMount

        Returns:
            ReparsePoint: New object using the binary stream as source
        '''
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])
        nw_obj = cls()

        #reparse_tag (type, flags) data_len, guid, data
        nw_obj.reparse_flag = ReparseFlags((content[0] & 0xF0000000) >> 28)
        nw_obj.reparse_type = ReparseType(content[0] & 0x0000FFFF)
        guid = None #guid exists only in third party reparse points
        if nw_obj.reparse_flag & ReparseFlags.IS_MICROSOFT:#a microsoft tag
            if nw_obj.reparse_type is ReparseType.MOUNT_POINT or nw_obj.reparse_type is ReparseType.SYMLINK:
                data = JunctionOrMount.create_from_binary(binary_view[cls._REPR.size:])
            else:
                data = binary_view[cls._REPR.size:].tobytes()
        else:
            guid = binary_view[cls._REPR.size:cls._REPR.size+16].tobytes()
            data = binary_view[cls._REPR.size+len(guid):].tobytes()
        nw_obj.data_len, nw_obj.guid, nw_obj.data = content[1], guid, data

        return nw_obj

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(reparse_flags={!s}, reparse_type={!s}, data_len={}, guid={}, data={})'.format(
            self.reparse_type, self.reparse_flags, self.data_len, self.guid, self.data)

#******************************************************************************
# EA_INFORMATION ATTRIBUTE
#******************************************************************************
class EaInformation(AttributeContentRepr):
    _REPR = struct.Struct("<2HI")
    ''' Size of Extended Attribute entry - 2
        Number of Extended Attributes which have NEED_EA set - 2
        Size of extended attribute data - 4
    '''
    # def __init__(self, point_view):
    #     self.entry_len, self.ea_set_number, self.ea_size = \
    #         EaInformation._REPR.unpack(point_view[:EaInformation._REPR.size])

    def __init__(self, content=(None,)*3):
        self.entry_len, self.ea_set_number, self.ea_size = content

    @classmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        return cls(cls._REPR.unpack(binary_stream[:cls._REPR.size]))

    def __len__(self):
        '''Returns the logical size of the file'''
        return cls._REPR.size

    def __eq__(self, other):
        if isinstance(other, EaInformation):
            return self.entry_len == other.entry_len and self.ea_set_number == other.ea_set_number \
                and self.ea_size == other.ea_size
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(entry_len={self.entry_len}, ea_set_number={self.ea_set_number}, ea_size={self.ea_size})'

#******************************************************************************
# EA ATTRIBUTE
#******************************************************************************
class EaEntry(AttributeContentRepr):
    _REPR = struct.Struct("<I2BH")
    ''' Offset to the next EA  - 4
        Flags - 1
        Name length - 1
        Value length - 2
    '''

    def __init__(self, content=(None,)*4):
        '''Creates a EaEntry object. The content has to be an iterable
        with precisely 6 elements in order.
        If content is not provided, a 6 element tuple, where all elements are
        None, is the default argument

        Args:
            content (iterable), where:
                [0] (int) - Offset to the next EA
                [1] (int) - Flags
                [2] (str) - name
                [3] (bytes) - value
        '''
        self.offset_next_ea, self.flags, self.name, self.value = content

    def _get_name_len(self):
        return len(self.name)

    def _get_value_len(self):
        return len(self.value)

    #the name length can derived from the name, so, we don't need to keep in memory
    name_len = property(_get_name_len, doc='Length of the name')
    value_len = property(_get_value_len, doc='Length of the value')

    @classmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        content = cls._REPR.unpack(binary_stream[:cls._REPR.size])
        nw_obj = cls()

        _MOD_LOGGER.debug(f"Creating EaEntry from binary '{binary_stream.tobytes()}'...")
        name = binary_stream[cls._REPR.size:cls._REPR.size + content[2]].tobytes().decode("ascii")
        #it looks like the value is 8 byte aligned, do some math to compensate
        #TODO confirm if this is true
        value_alignment = (_ceil((cls._REPR.size + content[2]) / 8) * 8)
        value = binary_stream[value_alignment:value_alignment + content[3]].tobytes()
        #value = binary_stream[cls._REPR.size + content[2]:cls._REPR.size + content[2] + content[3]].tobytes()

        nw_obj.offset_next_ea, nw_obj.flags, nw_obj.name, nw_obj.value = \
            content[0], content[1], name, value

        _MOD_LOGGER.debug(f"New EaEntry {repr(nw_obj)}")

        return nw_obj

    def __len__(self):
        '''Returns the size of the entry'''
        return self.offset_next_ea

    def __eq__(self, other):
        if isinstance(other, EaEntry):
            return self.offset_next_ea == other.offset_next_ea and self.flags == other.flags \
                and self.name == other.name and self.value == other.value
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(offset_next_ea={self.offset_next_ea}, flags={self.flags}, name={self.name}, value={self.value}, name_len={self.name_len}, value_len={self.value_len})'

class Ea(AttributeContentNoRepr):
    def __init__(self, content):
        self.ea_list = content

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        ea_list = []
        offset = 0

        _MOD_LOGGER.debug(f"Creating Ea object from binary stream {binary_stream.tobytes()}...")
        while True:
            entry = EaEntry.create_from_binary(binary_stream[offset:])
            offset += len(entry)
            ea_list.append(entry)
            if offset >= len(binary_stream):
                break
            _MOD_LOGGER.debug(f"Next EaEntry offset = {offset}")
        _MOD_LOGGER.debug(f"Ea object created successfully. {ea_list}")

        return cls(ea_list)

    def __iter__(self):
        '''Return the iterator for the representation of the list, so it is
        easier to check everything'''
        return iter(self.ea_list)

    def __getitem__(self, index):
        '''Return the AttributeListEntry at the specified position'''
        return _getitem(self.ea_list, index)

    def __len__(self):
        '''Returns the logical size of the file'''
        return len(self.ea_list)

    def __eq__(self, other):
        if isinstance(other, Ea):
            return self.ea_list == other.ea_list
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f"(ea_list={self.ea_list})"

#******************************************************************************
# SECURITY_DESCRIPTOR ATTRIBUTE
#******************************************************************************
class SecurityDescriptorHeader(AttributeContentRepr):
    _REPR = struct.Struct("<B1xH4I")
    ''' Revision number - 1
        Padding - 1
        Control flags - 2
        Reference to the owner SID - 4 (offset relative to the header)
        Reference to the group SID - 4 (offset relative to the header)
        Reference to the DACL - 4 (offset relative to the header)
        Reference to the SACL - 4 (offset relative to the header)
    '''

    def __init__(self, content=(None,)*6):
        self.revision_number, self.control_flags, self.owner_sid_offset,\
        self.group_sid_offset, self.dacl_offset, self.sacl_offset = content

    @classmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        nw_obj = cls(cls._REPR.unpack(binary_stream))
        nw_obj.control_flags = SecurityDescriptorFlags(nw_obj.control_flags)

        return nw_obj

    def __len__(self):
        '''Returns the logical size of the file'''
        return cls._REPR.size

    def __eq__(self, other):
        if isinstance(other, SecurityDescriptorHeader):
            return self.revision_number == other.revision_number \
                and self.control_flags == other.control_flags \
                and self.owner_sid_offset == other.owner_sid_offset and self.group_sid_offset == other.group_sid_offset \
                and self.dacl_offset == other.dacl_offset and self.sacl_offset == other.sacl_offset
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(revision_number={self.revision_number}, control_flags={str(self.control_flags)}, owner_sid_offset={self.owner_sid_offset}, group_sid_offset={self.group_sid_offset}, dacl_offset={self.dacl_offset}, sacl_offset={self.sacl_offset})'

class ACEHeader(AttributeContentRepr):
    _REPR = struct.Struct("<2BH")
    ''' ACE Type - 1
        ACE Control flags - 1
        Size - 2 (includes header size)
    '''

    def __init__(self, content=(None,)*3):
        self.type, self.control_flags, self.ace_size = content

    @classmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        nw_obj = cls()
        content = cls._REPR.unpack(binary_stream)

        nw_obj.type, nw_obj.control_flags, nw_obj.ace_size, = ACEType(content[0]), \
            ACEControlFlags(content[1]), content[2]

        return nw_obj

    def __len__(self):
        '''Returns the logical size of the file'''
        return cls._REPR.size

    def __eq__(self, other):
        if isinstance(other, ACEHeader):
            return self.type == other.type \
                and self.control_flags == other.control_flags \
                and self.ace_size == other.ace_size
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(type={self.type}, control_flags={str(self.control_flags)}, ace_size={str(self.ace_size)})'

class SID(AttributeContentRepr):
    _REPR = struct.Struct("<2B6s")
    ''' Revision number - 1
        Number of sub authorities - 1
        Authority - 6
        Array of 32 bits with sub authorities - 4 * number of sub authorities
    '''

    def __init__(self, content=(None,)*3, sub_authorities=None):
        self.revision_number, _, self.authority = content
        self.sub_authorities = sub_authorities

    def _get_sub_authority_len(self):
        return len(self.sub_authorities)

    #the name length can derived from the name, so, we don't need to keep in memory
    sub_auth_len = property(_get_sub_authority_len, doc='Quantity of sub authorities')

    @classmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        content = cls._REPR.unpack(binary_stream[:cls._REPR.size])
        if content[1]:
            sub_auth_repr = struct.Struct("<" + str(content[1]) + "I")
            sub_auth = sub_auth_repr.unpack(binary_stream[cls._REPR.size:cls._REPR.size + sub_auth_repr.size])
        else:
            sub_auth = ()

        nw_obj = cls(content, sub_auth)
        nw_obj.authority = int.from_bytes(content[2], byteorder="big")

        return nw_obj

    def __len__(self):
        '''Returns the size of the SID in bytes'''
        return SID._REPR.size + (4 * sub_auth_len)

    def __eq__(self, other):
        if isinstance(other, SID):
            return self.revision_number == other.revision_number \
                and self.authority == other.authority \
                and self.sub_authorities == other.sub_authorities
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(revision_number={self.revision_number}, sub_auth_len={self.sub_auth_len}, authority={self.authority}, sub_authorities={self.sub_authorities})'

    def __str__(self):
        'Return a nicely formatted representation string'
        sub_auths = "-".join([str(sub) for sub in self.sub_authorities])
        return f'S-{self.revision_number}-{self.authority}-{sub_auths}'

class BasicACE(AttributeContentRepr):
    _REPR = struct.Struct("<I")
    ''' Access rights flags - 4
        SID - n
    '''

    def __init__(self, content=(None,)*2):
        self.access_rights_flags, self.sid = content

    @classmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        access_flags = cls._REPR.unpack(binary_stream[:cls._REPR.size])[0]
        sid = SID.create_from_binary(binary_stream[cls._REPR.size:])

        nw_obj = cls((ACEAccessFlags(access_flags), sid))

        return nw_obj

    def __len__(self):
        '''Returns the logical size of the file'''
        return cls._REPR.size

    def __eq__(self, other):
        if isinstance(other, BasicACE):
            return self.access_rights_flags == other.access_rights_flags \
                and self.sid == other.sid
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(access_rights_flags={str(self.access_rights_flags)}, sid={str(self.sid)})'

class ObjectACE(AttributeContentRepr):
    _REPR = struct.Struct("<2I16s16s")
    ''' Access rights flags - 4
        Flags - 4
        Object type class identifier (GUID) - 16
        Inherited object type class identifier (GUID) - 16
        SID - n
    '''

    def __init__(self, content=(None,)*5):
        self.access_rights_flags, self.flags, self.object_guid,
        self.inherited_guid, self.sid = content

    @classmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        content = cls._REPR.unpack(binary_stream[cls._HEADER_SIZE:cls._HEADER_SIZE + cls._REPR.size])
        sid = SID.create_from_binary(binary_stream[cls._HEADER_SIZE + cls._REPR.size:])

        nw_obj = cls((ACEAccessFlags(content[0]), content[1], UUID(bytes_le=content[2]), UUID(bytes_le=content[3]), sid))

        return nw_obj

    def __len__(self):
        '''Returns the logical size of the file'''
        return cls._REPR.size + len(self.sid)

    def __eq__(self, other):
        if isinstance(other, ObjectACE):
            return self.access_rights_flags == other.access_rights_flags \
                and self.flags == other.flags and self.object_guid == other.object_guid \
                and self.inherited_guid == other.inherited_guid and self.sid == other.sid
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(access_rights_flags={self.access_rights_flags}, flags={self.flags}, object_guid={self.object_guid}, inherited_guid={self.inherited_guid}, sid={self.sid})'

class CompoundACE():
    '''Nobody knows this structure'''
    pass

class ACE(AttributeContentNoRepr):
    _HEADER_SIZE = ACEHeader.get_representation_size()

    def __init__(self, content=(None,)*3):
        self.header, self.basic_ace, self.object_ace = content

    @classmethod
    def create_from_binary(cls, binary_stream):
        nw_obj = cls()
        header = ACEHeader.create_from_binary(binary_stream[:cls._HEADER_SIZE])

        nw_obj.header = header

        #TODO create a _dispatcher and replace this slow ass comparison
        if "OBJECT" in header.type.name:
            nw_obj.object_ace = ObjectACE.create_from_binary(binary_stream[cls._HEADER_SIZE:])
        elif "COMPOUND" in header.type.name:
            pass
        else:
            #self.basic_ace = BasicACE.create_from_binary(binary_stream[cls._HEADER_SIZE:header.ace_size - cls._HEADER_SIZE])
            nw_obj.basic_ace = BasicACE.create_from_binary(binary_stream[cls._HEADER_SIZE:])

        return nw_obj


    def __len__(self):
        '''Returns the logical size of the file'''
        return self.header.ace_size

    def __eq__(self, other):
        if isinstance(other, ACE):
            return self.header == other.header \
                and self.basic_ace == other.basic_ace and self.object_ace == other.object_ace
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f"(header={self.header}, basic_ace={self.basic_ace}, object_ace={self.object_ace})"

class ACL(AttributeContentRepr):
    _REPR = struct.Struct("<B1x2H2x")
    ''' Revision number - 1
        Padding - 1
        Size - 2
        ACE Count - 2
        Padding - 2
    '''

    def __init__(self, content=(None,)*3, aces=None):
        self.revision_number, self.size, _ = content
        self.aces = aces

    def _get_aces_len(self):
        return len(self.aces)

    #the name length can derived from the name, so, we don't need to keep in memory
    aces_len = property(_get_aces_len, doc='Quantity of ACE objects')

    @classmethod
    def get_representation_size(cls):
        '''Get the representation size in bytes, based on defined struct'''
        return cls._REPR.size

    @classmethod
    def create_from_binary(cls, binary_stream):
        '''Create the class from a binary stream'''
        content = cls._REPR.unpack(binary_stream[:cls._REPR.size])
        aces = []

        offset = cls._REPR.size
        for i in range(content[2]):
            ace = ACE.create_from_binary(binary_stream[offset:])
            offset += len(ace)
            aces.append(ace)
            _MOD_LOGGER.debug(f"Next ACE offset = {offset}")

        if len(aces) != content[2]:
            raise ContentError("Number of processed ACE entries different than expected.")

        nw_obj = cls(content, aces)

        return nw_obj

    def __len__(self):
        '''Returns the logical size of the file'''
        return self.size

    def __eq__(self, other):
        if isinstance(other, ACL):
            return self.revision_number == other.revision_number \
                and self.size == other.size and self.aces == other.aces
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f'(revision_number={self.revision_number}, size={self.size}, aces_len={self.aces_len}, aces={self.aces})'

class SecurityDescriptor(AttributeContentNoRepr):
    def __init__(self, content=(None,)*5):
        self.header, self.owner_sid, self.group_sid, self.sacl, self.dacl = content

    @classmethod
    def create_from_binary(cls, binary_stream):
        header = SecurityDescriptorHeader.create_from_binary(binary_stream[:SecurityDescriptorHeader.get_representation_size()])

        owner_sid = SID.create_from_binary(binary_stream[header.owner_sid_offset:])
        group_sid = SID.create_from_binary(binary_stream[header.group_sid_offset:])
        dacl = None
        sacl = None

        if header.sacl_offset:
            sacl = ACL.create_from_binary(binary_stream[header.sacl_offset:])
        if header.dacl_offset:
            dacl = ACL.create_from_binary(binary_stream[header.dacl_offset:])

        #if header.usage_flags & MftUsageFlags.IN_USE:
        #acl = ACL.create_from_binary(binary_stream[header.sacl])
        nw_obj = cls((header, owner_sid, group_sid, sacl, dacl))

        print(nw_obj)

        return nw_obj


    def __len__(self):
        '''Returns the logical size of the file'''
        pass
        #return len(self.ea_list)

    def __eq__(self, other):
        if isinstance(other, SecurityDescriptor):
            pass
            #return self.ea_list == other.ea_list
        return False

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + f"(header={self.header}, owner_sid={str(self.owner_sid)}, group_sid={str(self.group_sid)}, sacl={str(self.sacl)}, dacl={str(self.dacl)})"

#******************************************************************************
# LOGGED_TOOL_STREAM ATTRIBUTE
#******************************************************************************
class LoggedToolStream():
    #TODO implement the know cases of this attribute
    def __init__(self, bin_view):
        '''Initialize the class. Expects the binary_view that represents the
        content. Size information is derived from the content.
        '''
        self.content = bin_view.tobytes()

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(content={})'.format(
            self.content)

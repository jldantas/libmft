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

from libmft.util.functions import convert_filetime, get_file_reference
from libmft.exceptions import AttrContentException
from libmft.flagsandtypes import AttrTypes, NameType, FileInfoFlags, \
    IndexEntryFlags, VolumeFlags, ReparseType, ReparseFlags

MOD_LOGGER = logging.getLogger(__name__)

#TODO verify, in general, if it is not better to encode the data within the
#attributes as tuple or list and use properties to access by name

#******************************************************************************
# STANDARD_INFORMATION ATTRIBUTE
#******************************************************************************
class StandardInformation():
    '''Represents the STANDARD_INFORMATION converting the timestamps to
    datetimes and the flags to FileInfoFlags representation.
    '''
    _REPR = struct.Struct("<4Q4I")
    _REPR_NFTS_3_EXTENSION = struct.Struct("<2I2Q")
    ''' Creation time - 8
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

    def __init__(self, content=(None,)*12):
        '''Creates a StandardInformation object. The content has to be an iterable
        with precisely 12 objects in order. Creation of the object from a binary
        string/memoryview can be done using the class method 'create_from_binary'
        '''
        self.timestamps = {}

        self.timestamps["created"], self.timestamps["changed"], \
        self.timestamps["mft_change"], self.timestamps["accessed"], \
        self.flags, self.max_n_ver, self.ver_n, self.class_id, self.owner_id, \
        self.security_id, self.quota_charged, self.usn = content

        if self.flags is not None: #we might have an "empty" oject, so convert only if it is valid
            #flags and timestaps have specific format, so we convert them
            self.timestamps["created"] = convert_filetime(self.timestamps["created"])
            self.timestamps["changed"] = convert_filetime(self.timestamps["changed"])
            self.timestamps["mft_change"] = convert_filetime(self.timestamps["mft_change"])
            self.timestamps["accessed"] = convert_filetime(self.timestamps["accessed"])
            self.flags = FileInfoFlags(self.flags)

    @classmethod
    def get_content_size(cls):
        '''Return the size of the STANDARD_INFORMATION content, always considering
        a NFTS version >3.'''
        return cls._REPR.size + cls._REPR_NFTS_3_EXTENSION.size

    @classmethod
    def create_from_binary(cls, binary_view):
        main_content = cls._REPR.unpack(binary_view[:cls._REPR.size])
        if len(binary_view) != cls._REPR.size:
            ntfs3_extension = cls._REPR_NFTS_3_EXTENSION.unpack(binary_view[cls._REPR.size:])
        else:
            ntfs3_extension = (None, None, None, None)

        return cls(_chain(main_content, ntfs3_extension))

    def get_created_time(self):
        '''Return the created time. This function provides the same information
        as using <variable>.timestamps["created"]'''
        return self.timestamps["created"]

    def get_changed_time(self):
        '''Return the changed time. This function provides the same information
        as using <variable>.timestamps["changed"]'''
        return self.timestamps["changed"]

    def get_mftchange_time(self):
        '''Return the mft change time. This function provides the same information
        as using <variable>.timestamps["mft_change"]'''
        return self.timestamps["mft_change"]

    def get_accessed_time(self):
        '''Return the accessed time. This function provides the same information
        as using <variable>.timestamps["accessed"]'''
        return self.timestamps["accessed"]

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(timestamps={}, flags={!s}, max_n_ver={}, ver_n={}, class_id={}, owner_id={}, security_id={}, quota_charged={}, usn={})'.format(
            self.timestamps, self.flags, self.max_n_ver, self.ver_n, self.class_id,
            self.owner_id, self.security_id, self.quota_charged, self.usn)

#******************************************************************************
# ATTRIBUTE_LIST ATTRIBUTE
#******************************************************************************
class AttributeListEntry():
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

    def __init__(self, content=(None,)*8):
        '''Creates a AttributeListEntry object. The content has to be an iterable
        with precisely 8 objects in order. Creation of the object from a binary
        string/memoryview can be done using the class method 'create_from_binary'''
        self.attr_type, self.entry_len, name_len, self.name_offset, \
        self.start_vcn, file_coded_reference, self.attr_id, self.name = content

        if self.attr_type is not None:
            self.attr_type = AttrTypes(self.attr_type)
            self.file_ref, self.file_seq = get_file_reference(file_coded_reference)
        else:
            self.file_ref, self.file_seq = None, None

    def _get_name_length(self):
        '''Returns the length of the name based on the name'''
        if self.name is None:
            return 0
        else:
            return len(self.name)

    #the name length can derived from the name, so, we don't need to keep in memory
    name_len = property(_get_name_length, doc='Length of the name')

    @classmethod
    def create_from_binary(cls, binary_view):
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])
        if content[2]:
            name = binary_view[content[3]:content[3]+(2*content[2])].tobytes().decode("utf_16_le")
        else:
            name = None

        return cls(_chain(content, (name,)))

    def __len__(self):
        '''Returns the size of the entry, in bytes'''
        return self.entry_len

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(attr_type={!s}, entry_len={}, name_len={}, name_offset={}, start_vcn={}, file_ref={}, file_seq={}, attr_id={}, name={})'.format(
            self.attr_type, self.entry_len, self.name_len, self.name_offset,
            self.start_vcn, self.file_ref, self.file_seq, self.attr_id, self.name)

class AttributeList():
    '''Represents the ATTRIBUTE_LIST attribute, holding all the entries, if available,
    as AttributeListEntry objects.'''

    def __init__(self, content=[]):
        '''Creates an AttributeList content representation. Content has to be a
        list of AttributeListEntry that will be referred by the object. To create
        from a binary string, use the function 'create_from_binary' '''
        #TODO change from list to dict?
        self.attr_list = content

    @classmethod
    def create_from_binary(cls, binary_view):
        attr_list = []
        offset = 0

        while True:
            entry = AttributeListEntry.create_from_binary(binary_view[offset:])
            offset += entry.entry_len
            attr_list.append(entry)
            if offset >= len(binary_view):
                break

        return cls(attr_list)

    def __len__(self):
        '''Return the number of entries in the attribute list'''
        return len(self.attr_list)

    def __iter__(self):
        '''Return the iterator for the representation of the list, so it is
        easier to check everything'''
        return iter(self.attr_list)

    def __getitem__(self, index):
        return self.attr_list[index]

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(attr_list={})'.format(
            self.attr_list)

#******************************************************************************
# OBJECT_ID ATTRIBUTE
#******************************************************************************
class UID():
    _REPR = struct.Struct("<2Q")
    ''' Object ID - 8
        Volume ID - 8
        https://msdn.microsoft.com/en-us/library/cc227517.aspx
    '''
    def __init__(self, uid_view):
        self.object_id, self.volume_id = UID._REPR.unpack(uid_view[:UID._REPR.size])

    @classmethod
    def get_uid_size(cls):
        return cls._REPR.size

    #TODO comparison methods

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(volume_id={:#010x}, object_id={:#010x})'.format(
            self.volume_id, self.object_id)

class ObjectID():
    def __init__(self,  content=(None,)*4):
        uid_size = UID.get_uid_size()

        self.object_id, self.birth_vol_id, self.birth_object_id, \
        self.birth_domain_id = content

    @classmethod
    def create_from_binary(cls, binary_view):
        uid_size = UID.get_uid_size()

        uids = [UID(binary_view[i*uid_size:(i+1)*uid_size]) if i * uid_size < len(binary_view) else None for i in range(0,4)]

        return cls(uids)

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(object_id={}, birth_vol_id={}, birth_object_id={}, birth_domain_id={})'.format(
            self.object_id, self.birth_vol_id, self.birth_object_id, self.birth_domain_id)

#******************************************************************************
# VOLUME_NAME ATTRIBUTE
#******************************************************************************
class VolumeName():
    def __init__(self, name):
        self.name = name

    @classmethod
    def create_from_binary(cls, binary_view):
        name = binary_view.tobytes().decode("utf_16_le")

        return cls(name)

    def __len__(self):
        return len(self.name)

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(name={})'.format(
            self.name)

#******************************************************************************
# VOLUME_INFORMATION ATTRIBUTE
#******************************************************************************
class VolumeInformation():
    _REPR = struct.Struct("<Q2BH")
    ''' Unknow - 8
        Major version number - 1
        Minor version number - 1
        Volume flags - 2
    '''

    def __init__(self, content=(None,)*4):
        #self._unknow = temp[0]
        _, self.major_ver, self.minor_ver, self.vol_flags = content
        self.vol_flags = VolumeFlags(self.vol_flags)

    @classmethod
    def create_from_binary(cls, binary_view):
        return cls(cls._REPR.unpack(binary_view))

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(major_ver={}, minor_ver={}, vol_flags={!s})'.format(
            self.major_ver, self.minor_ver, self.vol_flags)

#******************************************************************************
# FILENAME ATTRIBUTE
#******************************************************************************
class FileName():
    '''Represents the FILE_NAME converting the timestamps to
    datetimes and the flags to FileInfoFlags representation.
    '''
    _REPR = struct.Struct("<7Q2I2B")
    ''' File reference to parent directory - 8
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

    def __init__(self, content=(None, )*12):
        '''Creates a FILE_NAME object. "attr_view" is the full attribute
        content, where the first bytes is the beginning of the content of the
        attribute'''
        self.timestamps = {}

        parent_coded_reference, self.timestamps["created"], \
        self.timestamps["changed"], self.timestamps["mft_change"], \
        self.timestamps["accessed"], self.allocated_file_size, self.file_size, \
        self.flags, self.reparse_value, name_len, self.name_type, \
        self.name = content

        if parent_coded_reference is not None:
            self.parent_ref, self.parent_seq = get_file_reference(parent_coded_reference)
            self.timestamps["created"] = convert_filetime(self.timestamps["created"])
            self.timestamps["changed"] = convert_filetime(self.timestamps["changed"])
            self.timestamps["mft_change"] = convert_filetime(self.timestamps["mft_change"])
            self.timestamps["accessed"] = convert_filetime(self.timestamps["accessed"])
            self.flags = FileInfoFlags(self.flags)
            self.name_type = NameType(self.name_type)
        else:
            self.parent_ref, self.parent_seq = None, None

        if len(self.name) != self.name_len:
            MOD_LOGGER.error("Expected file name size does not match.")
            raise AttrContentException("Error processing FILE_NAME Attr. File name size does not match")

    def _get_name_len(self):
        return len(self.name)

    #the name length can derived from the name, so, we don't need to keep in memory
    name_len = property(_get_name_len, doc='Length of the name')

    @classmethod
    def create_from_binary(cls, binary_view):
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])
        name = binary_view[cls._REPR.size:].tobytes().decode("utf_16_le")

        return cls(_chain(content, (name,)))

    def get_created_time(self):
        '''Return the created time. This function provides the same information
        as using <variable>.timestamps["created"]'''
        return self.timestamps["created"]

    def get_changed_time(self):
        '''Return the changed time. This function provides the same information
        as using <variable>.timestamps["changed"]'''
        return self.timestamps["changed"]

    def get_mftchange_time(self):
        '''Return the mft change time. This function provides the same information
        as using <variable>.timestamps["mft_change"]'''
        return self.timestamps["mft_change"]

    def get_accessed_time(self):
        '''Return the accessed time. This function provides the same information
        as using <variable>.timestamps["accessed"]'''
        return self.timestamps["accessed"]

    def __len__(self):
        '''Returns the size of the file, in bytes, as recorded by the FILE_NAME
        attribute. Be advised this can be wrong. The correct size should be parsed
        from the data attribute. Blame Microsoft.'''
        return self.file_size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(parent_ref={}, parent_seq={}, timestamps={}, allocated_file_size={}, file_size={}, flags={!s}, name_len={}, name_type={!s}, name={})'.format(
            self.parent_ref, self.parent_seq, self.timestamps, self.allocated_file_size,
            self.file_size, self.flags, self.name_len, self.name_type,
            self.name)

#******************************************************************************
# DATA ATTRIBUTE
#******************************************************************************
class Data():
    '''This is a placeholder class to the data attribute. By itself, it does
    very little and holds almost no information. If the data is resident, holds the
    content and the size.
    '''
    def __init__(self, bin_view):
        '''Initialize the class. Expects the binary_view that represents the
        content. Size information is derived from the content.
        '''
        self.content = bin_view.tobytes()

    def __len__(self):
        '''Returns the logical size of the file'''
        return len(self.content)

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(content={})'.format(
            self.content)

#******************************************************************************
# INDEX_ROOT ATTRIBUTE
#******************************************************************************
class IndexNodeHeader():
    '''Represents the Index Node Header, that is always present in the INDEX_ROOT
    and INDEX_ALLOCATION attribute.'''
    _REPR = struct.Struct("<4I")
    ''' Offset to start of index entry - 4
        Offset to end of used portion of index entry - 4
        Offset to end of the allocated index entry - 4
        Flags - 4
    '''

    def __init__(self, content):
        self.start_offset, self.end_offset, self.end_alloc_offset, \
        self.flags = content

    @classmethod
    def create_from_binary(cls, binary_view):
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])

        return cls(content)

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(start_offset={}, end_offset={}, end_alloc_offset={}, flags={})'.format(
            self.start_offset, self.end_offset, self.end_alloc_offset, self.flags)

class IndexEntry():
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
        #TODO don't save this here and overload later?
        self.generic, self.entry_len, self.content_len, self.flags, \
        self.content, self.vcn_child_node = content

        if self.flags is not None:
            self.flags = IndexEntryFlags(self.flags)

    @classmethod
    def create_from_binary(cls, binary_view, content_type=None):
        repr_size = cls._REPR.size
        content = cls._REPR.unpack(binary_view[:repr_size])

        vcn_child_node = (None,)
        if content_type is AttrTypes.FILE_NAME and content[2]:
            binary_content = FileName.create_from_binary(binary_view[repr_size:repr_size+content[2]])
        else:
            binary_content = binary_view[repr_size:repr_size+content[2]].tobytes()
        if content[3] & IndexEntryFlags.CHILD_NODE_EXISTS:
            temp_size = repr_size + content[2]
            boundary_fix = (content[1] - temp_size) % 8
            vcn_child_node = cls._REPR_VCN.unpack(binary_view[temp_size+boundary_fix:temp_size+boundary_fix+8])

        return cls(_chain(content, (binary_content,), vcn_child_node))

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(generic={}, entry_len={}, content_len={}, flags={!s}, content={}, vcn_child_node={})'.format(
            self.generic, self.entry_len, self.content_len, self.flags,
            self.content, self.vcn_child_node)

class IndexRoot():
    '''Represents the INDEX_ROOT'''
    _REPR = struct.Struct("<3IB3x")

    def __init__(self, content=(None,)*4, node_header=None, idx_entry_list=None):
        self.attr_type, self.collation_rule, self.index_len_in_bytes, \
        self.index_len_in_cluster = content
        self.node_header = node_header
        self.index_entry_list = idx_entry_list

        if self.attr_type:
            self.attr_type = AttrTypes(self.attr_type)

    @classmethod
    def create_from_binary(cls, binary_view):
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])
        node_header = IndexNodeHeader.create_from_binary(binary_view[cls._REPR.size:])
        index_entry_list = []
        attr_type = AttrTypes(content[0]) if content[0] else None

        offset = cls._REPR.size + node_header.start_offset
        while True:
            entry = IndexEntry.create_from_binary(binary_view[offset:], attr_type)
            index_entry_list.append(entry)
            if entry.flags & IndexEntryFlags.LAST_ENTRY:
                break
            else:
                offset += entry.entry_len

        return cls(content, node_header, index_entry_list)

    @classmethod
    def size(cls):
        return cls._REPR.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(attr_type={!s}, collation_rule={}, index_len_in_bytes={}, index_len_in_cluster={}, node_header={}, index_entry_list={})'.format(
            self.attr_type, self.collation_rule, self.index_len_in_bytes,
            self.index_len_in_cluster, self.node_header, self.index_entry_list)

#******************************************************************************
# BITMAP ATTRIBUTE
#******************************************************************************
class Bitmap():
    def __init__(self, bitmap_view):
        self._bitmap = bitmap_view.tobytes()

    #TODO write a function to allow query if a particular entry is allocated
    #TODO write a function to show all the allocated entries

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(bitmap={})'.format(
            self._bitmap)

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
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])
        repar_point_size = ReparsePoint.get_struct_size()

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
        self.reparse_type, self.reparse_flags, self.data_len, \
        self.guid, self.data = content

        if self.reparse_type:
            self.reparse_flags = ReparseFlags(self.reparse_flags)
            self.reparse_type = ReparseType(self.reparse_type)

        print(self)
    # def __init__(self, attr_view):
    #     temp = ReparsePoint._REPR.unpack(attr_view[:ReparsePoint._REPR.size])
    #
    #     self.reparse_flags = ReparseFlags((temp[0] & 0xF0000000) >> 28)
    #     self.data_len = temp[1]
    #     if self.reparse_flags & ReparseFlags.IS_MICROSOFT: #not a microsoft tag
    #         self.reparse_type = ReparseType(temp[0] & 0x0000FFFF)
    #         self.guid = None #guid exists only in third party reparse points
    #
    #         if self.reparse_type is ReparseType.MOUNT_POINT or self.reparse_type is ReparseType.SYMLINK:
    #             self.data = JunctionOrMount.create_from_binary(attr_view[ReparsePoint._REPR.size:])
    #         else:
    #             self.data = attr_view[ReparsePoint._REPR.size:].tobytes()
    #     else:
    #         self.reparse_type = temp[0] & 0x0000FFFF #we don't know how to interpret the third party tag, so put it raw
    #         self.guid = attr_view[ReparsePoint._REPR.size:ReparsePoint._REPR.size+16].tobytes()
    #         self.data = attr_view[ReparsePoint._REPR.size+len(self.guid):].tobytes()

    @classmethod
    def create_from_binary(cls, binary_view):
        content = cls._REPR.unpack(binary_view[:cls._REPR.size])

        #reparse_tag (type, flags) data_len, guid, data
        #TODO rework this. A lot of duplicated effort (create tuple, expand tuple, casting, etc)
        reparse_flag = (content[0] & 0xF0000000) >> 28
        reparse_type = content[0] & 0x0000FFFF
        guid = None #guid exists only in third party reparse points
        if reparse_flag & ReparseFlags.IS_MICROSOFT:#a microsoft tag
            if ReparseType(reparse_type) is ReparseType.MOUNT_POINT or reparse_type is ReparseType.SYMLINK:
                data = JunctionOrMount.create_from_binary(binary_view[cls._REPR.size:])
            else:
                data = binary_view[cls._REPR.size:].tobytes()
        else:
            guid = binary_view[cls._REPR.size:cls._REPR.size+16].tobytes()
            data = binary_view[cls._REPR.size+len(guid):].tobytes()

        return cls((reparse_type, reparse_flag, content[1], guid, data))

    @classmethod
    def get_struct_size(cls):
        return cls._REPR.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(reparse_flags={!s}, reparse_type={!s}, data_len={}, guid={}, data={})'.format(
            self.reparse_type, self.reparse_flags, self.data_len, self.guid, self.data)

#******************************************************************************
# EA_INFORMATION ATTRIBUTE
#******************************************************************************
class EaInformation():
    _REPR = struct.Struct("<2HI")
    ''' Size of Extended Attribute entry - 2
        Number of Extended Attributes which have NEED_EA set - 2
        Size of extended attribute data - 4
    '''
    def __init__(self, point_view):
        self.entry_len, self.ea_set_number, self.ea_size = \
            EaInformation._REPR.unpack(point_view[:EaInformation._REPR.size])

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(entry_len={}, ea_set_number={}, ea_size={})'.format(
            self.entry_len, self.ea_set_number, self.ea_size)

#******************************************************************************
# EA ATTRIBUTE
#******************************************************************************
class Ea():
    pass

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

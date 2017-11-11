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
    _REPR = struct.Struct("<4Q6I2Q")
    _REPR_NTFS_LE_3 = struct.Struct("<4Q4I")
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

    def __init__(self, attr_view):
        '''Creates a StandardInformation object. "attr_view" has to have the
        correct size for this attribute. It accounts for versions of NTFS < 3 and
        NTFS > 3.
        '''
        try:
            temp = self._REPR.unpack(attr_view)
            ntfs3_plus = True
        except struct.error:
            temp = self._REPR_NTFS_LE_3.unpack(attr_view)
            ntfs3_plus = False

        self.timestamps = {}
        self.timestamps["created"] = convert_filetime(temp[0])
        self.timestamps["changed"] = convert_filetime(temp[1])
        self.timestamps["mft_change"] = convert_filetime(temp[2])
        self.timestamps["accessed"] = convert_filetime(temp[3])
        self.flags = FileInfoFlags(temp[4])
        self.max_n_ver = temp[5]
        self.ver_n = temp[6]
        self.class_id = temp[7]
        if (ntfs3_plus):
            self.owner_id = temp[8]
            self.security_id = temp[9]
            self.quota_charged = temp[10]
            self.usn = temp[11]
        else:
            self.owner_id = None
            self.security_id = None
            self.quota_charged = None
            self.usn = None

    @classmethod
    def get_content_size(cls):
        '''Return the size of the STANDARD_INFORMATION content, always considering
        a NFTS version >3.'''
        return cls._REPR.size

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

    def __init__(self, entry_view):
        '''Creates a AttributeListEntry object. Expects that "entry_view" starts
        at the beginning of the entry. Once the basic information is loaded,
        find the correct size of the entry.'''
        temp = self._REPR.unpack(entry_view[:self._REPR.size])

        self.attr_type = AttrTypes(temp[0])
        self.entry_len = temp[1]
        self.name_len = temp[2]
        self.name_offset = temp[3]
        self.start_vcn = temp[4]
        self.file_ref, self.file_seq = get_file_reference(temp[5])
        self.attr_id = temp[6]
        if self.name_len:
            self.name = entry_view[self.name_offset:self.name_offset+(2*self.name_len)].tobytes().decode("utf_16_le")
        else:
            self.name = None

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
    def __init__(self, attr_view):
        #TODO change from list to dict?
        self.attr_list = []

        offset = 0
        while True:
            entry = AttributeListEntry(attr_view[offset:])
            offset += entry.entry_len
            self.attr_list.append(entry)
            if offset >= len(attr_view):
                break

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
    def __init__(self, attr_view):

        uid_size = UID.get_uid_size()

        self.object_id = None
        self.birth_vol_id = None
        self.birth_object_id = None
        self.birth_domain_id = None

        if len(attr_view) >= uid_size:
            self.object_id = UID(attr_view[:uid_size])
        if len(attr_view) >= uid_size * 2:
            self.birth_vol_id = UID(attr_view[2*uid_size:uid_size])
        if len(attr_view) >= uid_size * 3:
            self.birth_object_id = UID(attr_view[3*uid_size:uid_size])
        if len(attr_view) >= uid_size * 4:
            self.birth_domain_id = UID(attr_view[4*uid_size:uid_size])

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(object_id={}, birth_vol_id={}, birth_object_id={}, birth_domain_id={})'.format(
            self.object_id, self.birth_vol_id, self.birth_object_id, self.birth_domain_id)

#******************************************************************************
# VOLUME_NAME ATTRIBUTE
#******************************************************************************
class VolumeName():
    def __init__(self, name_view):
        self.name = name_view.tobytes().decode("utf_16_le")

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

    def __init__(self, attr_view):
        temp = self._REPR.unpack(attr_view)

        #self._unknow = temp[0]
        self.major_ver = temp[1]
        self.minor_ver = temp[2]
        self.vol_flags = VolumeFlags(temp[3])

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

    def __init__(self, attr_view):
        '''Creates a FILE_NAME object. "attr_view" is the full attribute
        content, where the first bytes is the beginning of the content of the
        attribute'''
        temp = self._REPR.unpack(attr_view[:self._REPR.size])

        self.timestamps = {}
        self.parent_ref, self.parent_seq = get_file_reference(temp[0])
        self.timestamps["created"] = convert_filetime(temp[1])
        self.timestamps["changed"] = convert_filetime(temp[2])
        self.timestamps["mft_change"] = convert_filetime(temp[3])
        self.timestamps["accessed"] = convert_filetime(temp[4])
        self.allocated_file_size = temp[5]
        self.file_size = temp[6]
        self.flags = FileInfoFlags(temp[7])
        self.reparse_value = temp[8]
        self.name_len = temp[9]
        self.name_type = NameType(temp[10])
        self.name = attr_view[self._REPR.size:].tobytes().decode("utf_16_le")
        if len(self.name) != self.name_len:
            MOD_LOGGER.error("Expected file name size does not match.")
            raise AttrContentException("Error processing FILE_NAME Attr. File name size does not match")

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
        self.size = len(bin_view)
        self.size_on_disk = len(bin_view)
        self.content = bin_view.tobytes()

    def __len__(self):
        '''Returns the logical size of the file'''
        return self.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(size={}, content={})'.format(
            self.size, self.content)

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

    def __init__(self, node_view):
        temp = IndexNodeHeader._REPR.unpack(node_view[:IndexNodeHeader._REPR.size])

        self.start_offset = temp[0]
        self.end_offset = temp[1]
        self.end_alloc_offset = temp[2]
        self.flags = temp[3]

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(start_offset={}, end_offset={}, end_alloc_offset={}, flags={})'.format(
            self.start_offset, self.end_offset, self.end_alloc_offset, self.flags)

class IndexEntry():
    _REPR = struct.Struct("<Q2HI")
    ''' Undefined - 8
        Length of entry - 2
        Length of content - 4
        Flags - 4
        Content - variable
        VCN of child node - 8 (exists only if flag is set, aligned to a 8 byte boundary)
    '''
    _REPR_VCN = struct.Struct("<Q")

    def __init__(self, entry_view, content_is_filename):
        temp = IndexEntry._REPR.unpack(entry_view[:IndexEntry._REPR.size])
        #TODO this looks like a terrible practice, redo!
        self._content_is_filename = content_is_filename

        self.generic = temp[0] #TODO don't save this here and overload later?
        self.entry_len = temp[1]
        self.content_len = temp[2]
        self.flags = IndexEntryFlags(temp[3])
        self.content = None
        self.vcn_child_node = None

        if content_is_filename:
            self.file_ref, self.file_seq = get_file_reference(temp[0])
            if self.content_len:
                self.content = FileName(entry_view[IndexEntry._REPR.size:IndexEntry._REPR.size+self.content_len])
        else:
            self.generic = temp[0] #TODO don't save this here and overload later?
            if self.content_len:
                self.contect = entry_view[IndexEntry._REPR.size:IndexEntry._REPR.size+self.content_len].tobytes()

        if self.flags & IndexEntryFlags.CHILD_NODE_EXISTS:
            temp_size = IndexEntry._REPR.size + self.content_len
            boundary_fix = (self.entry_len - IndexEntry._REPR.size + self.content_len) % 8
            self.vcn_child_node = IndexEntry._REPR_VCN.unpack(entry_view[temp_size+boundary_fix:temp_size+boundary_fix+8])[0]

    def __repr__(self):
        'Return a nicely formatted representation string'
        if self._content_is_filename:
            return self.__class__.__name__ + '(file_ref={}, file_seq={}, entry_len={}, content_len={}, flags={!s}, content={}, vcn_child_node={})'.format(
                self.file_ref, self.file_seq, self.entry_len, self.content_len,
                self.flags, self.content, self.vcn_child_node)
        else:
            return self.__class__.__name__ + '(generic={}, entry_len={}, content_len={}, flags={!s}, content={}, vcn_child_node={})'.format(
                self.generic, self.entry_len, self.content_len, self.flags,
                self.content, self.vcn_child_node)

class IndexRoot():
    '''Represents the INDEX_ROOT'''
    _REPR = struct.Struct("<3IB3x")

    def __init__(self, attr_view):
        temp = IndexRoot._REPR.unpack(attr_view[:IndexRoot._REPR.size])

        if temp[0]:
            self.attr_type = AttrTypes(temp[0])
        else:
            self.attr_type = None #TODO changing type in the middle is not good. review.
        self.collation_rule = temp[1] #TODO identify this?
        self.index_len_in_bytes = temp[2]
        self.index_len_in_cluster = temp[3]
        self.node_header = IndexNodeHeader(attr_view[IndexRoot._REPR.size:])
        self.index_entry_list = []

        offset = IndexRoot._REPR.size + self.node_header.start_offset
        while True:
            if self.attr_type is AttrTypes.FILE_NAME:
                entry = IndexEntry(attr_view[offset:], True)
            else:
                entry = IndexEntry(attr_view[offset:], False)
            self.index_entry_list.append(entry)
            if entry.flags & IndexEntryFlags.LAST_ENTRY:
                break
            else:
                offset += entry.entry_len

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
    def __init__(self, point_view):
        temp = JunctionOrMount._REPR.unpack(point_view[:JunctionOrMount._REPR.size])

        self.target_name = point_view[8+temp[0]:8+temp[0]+temp[1]].tobytes().decode("utf_16_le")
        self.print_name = point_view[8+temp[2]:8+temp[3]+temp[1]].tobytes().decode("utf_16_le")

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(target_name={}, print_name={})'.format(
            self.target_name, self.print_name)

class ReparsePoint():
    _REPR = struct.Struct("<IH2x")
    ''' Reparse type flags - 4
            Reparse tag - 4 bits
            Reserver - 12 bits
            Reparse type - 2
        Reparse data length - 2
        Padding - 2
    '''
    def __init__(self, attr_view):
        temp = ReparsePoint._REPR.unpack(attr_view[:ReparsePoint._REPR.size])

        self.reparse_flags = ReparseFlags((temp[0] & 0xF0000000) >> 28)
        self.data_len = temp[1]
        if self.reparse_flags & ReparseFlags.IS_MICROSOFT: #not a microsoft tag
            self.reparse_type = ReparseType(temp[0] & 0x0000FFFF)
            self.guid = None #guid exists only in third party reparse points

            if self.reparse_type is ReparseType.MOUNT_POINT or self.reparse_type is ReparseType.SYMLINK:
                self.data = JunctionOrMount(attr_view[ReparsePoint._REPR.size:])
            else:
                self.data = attr_view[ReparsePoint._REPR.size:].tobytes()
        else:
            self.reparse_type = temp[0] & 0x0000FFFF #we don't know how to interpret the third party tag, so put it raw
            self.guid = attr_view[ReparsePoint._REPR.size:ReparsePoint._REPR.size+16].tobytes()
            self.data = attr_view[ReparsePoint._REPR.size+len(self.guid):].tobytes()

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

'''
This module contains all the known information about attributes. In particular,
their content. By definition, as we have only the $MFT available for processing
we can't have any of the content in case of non-resident attributes.
That means that all the classes below EXPECT the attribute to be resident.

Calling the constructors for a non-resident attribute MAY lead to an unxpected
behaviour.
'''
import enum
import struct
import logging

from libmft.util.functions import convert_filetime, get_file_reference
from libmft.exceptions import AttrContentException
from libmft.flagsandtypes import AttrTypes, NameType, FileInfoFlags

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
        return self.__class__.__name__ + '(attr_list={}'.format(
            self.attr_list)

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
        return self.__class__.__name__ + '(parent_ref={}, parent_seq={}, timestamps={}, allocated_file_size={}, file_size={}, flags={!s}, name_len={}, name_type={!s}, name={}'.format(
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
        return self.__class__.__name__ + '(size={}, content={}'.format(
            self.size, self.content)

#******************************************************************************
# INDEX_ROOT ATTRIBUTE
#******************************************************************************
class IndexRoot():
    '''Represents the INDEX_ROOT
    '''
    #name is missing, as encoding changes. It is added in the
    #initialization of the instance
    _REPR = struct.Struct("<3IB3x")

    def __init__(self, attr_view):
        temp = self._REPR.unpack(attr_view[:self._REPR.size])

        if temp[0]:
            self.attr_type = AttrTypes(temp[0])
        else:
            self.attr_type = None #TODO changing type in the middle is not good. review.
        self.collation_rule = temp[1] #TODO identify this?
        self.index_len_in_bytes = temp[2]
        self.index_len_in_cluster = temp[3]

    @classmethod
    def size(cls):
        return cls._REPR.size

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '(attr_type={!s}, collation_rule={}, index_len_in_bytes={}, index_len_in_cluster={}'.format(
            self.attr_type, self.collation_rule, self.index_len_in_bytes,
            self.index_len_in_cluster)

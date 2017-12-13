# -*- coding: utf-8 -*-
''' This module holds all flags and types as defined by the library.
This way, we have consistent means of finding this information. (Hopefully)
'''
import enum

#******************************************************************************
# Types
#******************************************************************************
class MftSignature(enum.Enum):
    '''Identifies the possible types of MFT entries. Mainly used by
    the MFTHeader, signature
    '''
    FILE = b"FILE"
    BAAD = b"BAAD"

class AttrTypes(enum.Enum):
    '''Defines the possible MFT attributes types.'''
    STANDARD_INFORMATION = 0x10
    ATTRIBUTE_LIST = 0x20
    FILE_NAME = 0x30
    OBJECT_ID = 0X40
    SECURITY_DESCRIPTOR = 0x50
    VOLUME_NAME = 0x60
    VOLUME_INFORMATION = 0x70
    DATA = 0x80
    INDEX_ROOT = 0x90
    INDEX_ALLOCATION = 0xA0
    BITMAP = 0xB0
    REPARSE_POINT = 0xC0
    EA_INFORMATION = 0xD0
    EA = 0xE0
    #LOGGED_UTILITY_STREAM = 0x100   #NTFS < 3
    LOGGED_TOOL_STREAM = 0x100

class NameType(enum.Enum):
    '''Flags that define how the file name is encoded in the FILE_NAME attribute'''
    POSIX = 0x0
    WIN32 = 0x1
    DOS = 0x2
    WIN32_DOS = 0X3

class ReparseType(enum.Enum):
    '''Possible tags for a reparse point based on the winnt.h'''
    MOUNT_POINT = 0x0003
    SYMLINK = 0x000C
    HSM = 0x0004
    HSM2 = 0x0006
    SIS = 0x0008
    WIM = 0x0008
    CSV = 0x0009
    DFS = 0x000A
    DFSR = 0x0012
    DEDUP = 0x0013
    NFS = 0x0014
    FILE_PLACEHOLDER = 0x0015
    WOF = 0x0017
    WCI = 0x0018

class CollationRule(enum.Enum):
    '''Possible collation rules for the IndexRoot attribute'''
    COLLATION_BINARY = 0x00000000  #Binary. The first byte is most significant
    COLLATION_FILENAME = 0x00000001  #Unicode strings, case-insensitive
    COLLATION_UNICODE_STRING = 0x00000002  #Unicode strings, case-sensitive. Upper case letters should come first
    COLLATION_NTOFS_ULONG = 0x00000010  #Unsigned 32-bit little-endian integer
    COLLATION_NTOFS_SID = 0x00000011  #NT security identifier (SID)
    COLLATION_NTOFS_SECURITY_HASH = 0x00000012  #Security hash first, then NT security identifier
    COLLATION_NTOFS_ULONGS = 0x00000013  #An array of unsigned 32-bit little-endian integer values

#******************************************************************************
# Flags
#******************************************************************************
class FileInfoFlags(enum.IntFlag):
    '''Define the possible flags for the STANDARD_INFORMATION and FILE_NAME
    attributes'''
    READ_ONLY = 0x0001
    HIDDEN = 0x0002
    SYSTEM = 0x0004
    ARCHIVE = 0x0020
    DEVICE = 0x0040
    NORMAL = 0x0080
    TEMPORARY = 0x0100
    SPARSE_FILE = 0x0200
    REPARSE_POINT = 0x0400
    COMPRESSED = 0x0800
    OFFLINE = 0x1000
    CONTENT_NOT_INDEXED = 0x2000
    ENCRYPTED = 0x4000
    DIRECTORY = 0x10000000
    INDEX_VIEW = 0x20000000

class MftUsageFlags(enum.IntFlag):
    '''Identifies the possible uses of a MFT entry. If it is not
    used, a file or a directory. Mainly used be the MFTHeader, usage_flags
    '''
    IN_USE = 0x0001
    DIRECTORY = 0x0002

class AttrFlags(enum.IntFlag):
    '''Represents the possible flags for the AttributeHeader class.'''
    COMPRESSED = 0x0001
    ENCRYPTED = 0x4000
    SPARSE = 0x8000

class IndexEntryFlags(enum.IntFlag):
    '''Represents the possible flags for the IndexEntry class.'''
    CHILD_NODE_EXISTS = 0x01
    LAST_ENTRY = 0x02

class VolumeFlags(enum.IntFlag):
    '''Represents the possible flags for the VolumeInformation class.'''
    IS_DIRTY = 0x0001
    RESIZE_JOURNAL = 0x0002
    UPGRADE_NEXT_MOUNT = 0x0004
    MOUNTED_ON_NT4 = 0x0008
    DELETE_USN_UNDERWAY = 0x0010
    REPAIR_OBJECT_ID = 0x0020
    MODIFIED_BY_CHKDISK = 0x8000

class ReparseFlags(enum.IntFlag):
    '''Represents the possible flags for the ReparsePoint class.'''
    RESERVED = 0x1
    IS_ALIAS = 0x2
    IS_HIGH_LATENCY = 0x4
    IS_MICROSOFT = 0x8

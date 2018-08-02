# -*- coding: utf-8 -*-
'''
Contains all flags and standard types for MFT interpretation.

This module contains a collection of structures that are necessary to interpret
the MFT.

Only definitions of those are present in this module and follows the standard:

* ``enum.Enum`` - For types
* ``enum.IntFlag`` - For flags

.. moduleauthor:: Júlio Dantas <jldantas@gmail.com>
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

class ACEType(enum.Enum):
    ACCESS_ALLOWED_ACE_TYPE = 0x00
    ACCESS_DENIED_ACE_TYPE = 0x01
    SYSTEM_AUDIT_ACE_TYPE = 0x02
    SYSTEM_ALARM_ACE_TYPE = 0x03
    ACCESS_ALLOWED_COMPOUND_ACE_TYPE = 0x04
    ACCESS_ALLOWED_OBJECT_ACE_TYPE = 0x05
    ACCESS_DENIED_OBJECT_ACE_TYPE = 0x06
    SYSTEM_AUDIT_OBJECT_ACE_TYPE = 0x07
    SYSTEM_ALARM_OBJECT_ACE_TYPE = 0x08
    ACCESS_ALLOWED_CALLBACK_ACE_TYPE = 0x09
    ACCESS_DENIED_CALLBACK_ACE_TYPE = 0x0a
    ACCESS_ALLOWED_CALLBACK_OBJECT_ACE_TYPE = 0x0b
    ACCESS_DENIED_CALLBACK_OBJECT_ACE_TYPE = 0x0c
    SYSTEM_AUDIT_CALLBACK_ACE_TYPE = 0x0d
    SYSTEM_ALARM_CALLBACK_ACE_TYPE = 0x0e
    SYSTEM_AUDIT_CALLBACK_OBJECT_ACE_TYPE = 0x0f
    SYSTEM_ALARM_CALLBACK_OBJECT_ACE_TYPE = 0x10
    SYSTEM_MANDATORY_LABEL_ACE_TYPE = 0x11

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

class SymbolicLinkFlags(enum.IntFlag):
    '''Represents the possible flags for the SymbolicLink class.'''
    SYMLINK_FLAG_RELATIVE = 0x00000001

class SecurityDescriptorFlags(enum.IntFlag):
    '''Represents the possible flags for the SecurityDescriptor class.'''
    SE_OWNER_DEFAULTED = 0x0001
    SE_GROUP_DEFAULTED = 0x0002
    SE_DACL_PRESENT = 0x0004
    SE_DACL_DEFAULTED = 0x0008
    SE_SACL_PRESENT = 0x0010
    SE_SACL_DEFAULTED = 0x0020
    SE_DACL_AUTO_INHERIT_REQ = 0x0100
    SE_SACL_AUTO_INHERIT_REQ = 0x0200
    SE_DACL_AUTO_INHERITED = 0x0400
    SE_SACL_AUTO_INHERITED = 0x0800
    SE_DACL_PROTECTED = 0x1000
    SE_SACL_PROTECTED = 0x2000
    SE_RM_CONTROL_VALID = 0x4000
    SE_SELF_RELATIVE = 0x8000

class ACEControlFlags(enum.IntFlag):
    OBJECT_INHERIT_ACE = 0x01
    CONTAINER_INHERIT_ACE = 0x02
    NO_PROPAGATE_INHERIT_ACE = 0x04
    INHERIT_ONLY_ACE = 0x08
    SUCCESSFUL_ACCESS_ACE_FLAG = 0x40 #audit flag
    FAILED_ACCESS_ACE_FLAG = 0x80 #audit flag

class ACEAccessFlags(enum.IntFlag):
    DELETE = 0x00010000
    READ_CONTROL = 0x00020000
    WRITE_DAC = 0x00040000
    WRITE_OWNER = 0x00080000
    SYNCHRONIZE = 0x00100000
    ACCESS_SYSTEM_SECURITY = 0x01000000
    MAXIMUM_ALLOWED = 0x02000000
    GENERIC_ALL = 0x10000000
    GENERIC_EXECUTE = 0x20000000
    GENERIC_WRITE = 0x40000000
    GENERIC_READ = 0x80000000

class EAFlags(enum.IntFlag):
    NEED_EA = 0x80

# libmft

The idea is to have a portable, "fast" way of parsing/reading MFT records.

So far, there is no intention of implementing the ability of writing/editing
MFT

## Getting started

TODO

At the moment, this is still in development stage. Things are supposed to fail or break

### Prerequisites

Python >= 3.6

## TODO/Features/Roadmap?

### Basic

- [x] MFT Header
- [x] Attribute Header (no named/named)
- [x] Resident Attribute Header
- [x] Non-Resident Attribute Header
- [x] Data runs

### Attributes

- [x] STANDARD_INFORMATION
- [x] ATTRIBUTE_LIST
- [x] FILE_NAME
- [x] OBJECT_ID
- [ ] SECURITY_DESCRIPTOR
- [x] VOLUME_NAME
- [x] VOLUME_INFORMATION
- [x] DATA
- [x] INDEX_ROOT
- [ ] INDEX_ALLOCATION (As this is always non-resident, it will not be implemented for now)
- [x] BITMAP
- [x] REPARSE_POINT
- [x] EA_INFORMATION
- [ ] EA
- [ ] LOGGED_TOOL_STREAM

## CHANGELOG



## References:

https://flatcap.org/linux-ntfs/ntfs/concepts/attribute_header.html
https://github.com/libyal/libfsntfs/blob/master/documentation/New%20Technologies%20File%20System%20(NTFS).asciidoc#mft-entry-header
https://github.com/sleuthkit/sleuthkit/blob/develop/tsk/fs/tsk_ntfs.h

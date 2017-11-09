# libmft

The idea is to have a portable, "fast" way of parsing MFT records.

## Getting started

TODO

At the moment, this is still in development stage. Things are supposed to fail or break

### Prerequisites

Python >= 3.6

## TODO/Features/Roadmap?

### Basic

- [x] MFT Header
- [x] Attribute Header (unamed/named)
- [x] Resident Attribute Header
- [x] Non-Resident Attribute Header
- [x] Data runs

### Attributes

- [x] STANDARD_INFORMATION
- [x] ATTRIBUTE_LIST
- [x] FILE_NAME
- [ ] OBJECT_ID
- [ ] SECURITY_DESCRIPTOR
- [ ] VOLUME_NAME
- [ ] VOLUME_INFORMATION
- [x] DATA
- [ ] INDEX_ROOT
- [ ] INDEX_ALLOCATION
- [ ] BITMAP
- [ ] REPARSE_POINT
- [ ] EA_INFORMATION
- [ ] EA
- [ ] LOGGED_TOOL_STREAM

## CHANGELOG



## References:

https://flatcap.org/linux-ntfs/ntfs/concepts/attribute_header.html
https://github.com/libyal/libfsntfs/blob/master/documentation/New%20Technologies%20File%20System%20(NTFS).asciidoc#mft-entry-header
https://github.com/sleuthkit/sleuthkit/blob/develop/tsk/fs/tsk_ntfs.h

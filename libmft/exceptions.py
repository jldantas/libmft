# -*- coding: utf-8 -*-
'''
This module contains all the exceptions that can be raised by the library.

It is important to note that some other core language exceptions can still
be raised.

Exceptions hierachy
- MFTException
|-- MFTError
|-- FixUpError
|-- EntryError
||--- HeaderError
||--- DataStreamError
'''

#TODO configure this based on the level of logging
_MESSAGE_LEVEL = 1
'''
0 - Basic
1 - Normal
2 - Debug
'''

def set_message_level(level):
    global _MESSAGE_LEVEL
    _MESSAGE_LEVEL = level

class MFTException(Exception):
    '''Base exception for all the exceptions defined by the library.'''
    pass

class MFTError(MFTException):
    pass

class FixUpError(MFTException):
    def __init__(self, msg):
        super().__init__(msg)
        pass

class EntryError(MFTException):
    '''Base exception for all the exceptions defined by the library.'''
    def __init__(self, msg, entry_binary, entry_number):
        '''All exceptions, at a minimum, have to have a message and the number
        of the entry related'''
        super().__init__(msg)
        self._entry_number = entry_number
        self._entry_binary = entry_binary

    def update_entry_number(self, entry_number):
        self._entry_number = entry_number

    def update_entry_binary(self, entry_binary):
        self._entry_binary = entry_binary

    def __str__(self):
        if _MESSAGE_LEVEL == 1:
            msg = f"\nEntry number: {self._entry_number}"
        elif _MESSAGE_LEVEL == 2:
            msg = f"\nEntry number: {self._entry_number}\nEntry binary: {self._entry_binary}"
        else:
            msg = ""

        return "".join((super().__str__(), msg))

class DataStreamError(EntryError):
    def __init__(self, msg):
        super().__init__(msg, None, -1)

class HeaderError(EntryError):
    def __init__(self, msg, header_name):
        super().__init__(msg, None, -1)
        self._header_name = header_name

    def __str__(self):
        basic_info = super().__str__()
        msg = f"\nHeader type: {self._header_name}"

        return "".join((basic_info, msg))

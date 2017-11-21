
'''
Exceptions hierachy
- MFTException
-- HeaderError
-- FixUpError


--- HeaderException
------ MFTHeaderException
------ AttrHeaderException
--- AttrContentException
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

class FixUpError(MFTException):
    def __init__(self, msg):
        super().__init__(msg, None, None)
        pass

class HeaderError(MFTException):
    def __init__(self, msg, entry_number=-1):
        super().__init__(msg, None, entry_number)
        pass

class HeaderException(MFTException):
    def __init__(self, msg, entry_number):
        '''All exceptions, at a minimum, have to have a message'''
        super().__init__(msg, entry_number)

class MFTHeaderException(HeaderException):
    def __init__(self, msg, entry_number=-1):
        '''All exceptions, at a minimum, have to have a message'''
        super().__init__(msg, entry_number)

class AttrHeaderException(HeaderException):
    def __init__(self, msg, entry_number=-1):
        '''All exceptions, at a minimum, have to have a message'''
        super().__init__(msg, entry_number)

class AttrContentException(MFTException):
    def __init__(self, msg, entry_number=-1):
        '''All exceptions, at a minimum, have to have a message'''
        super().__init__(msg, entry_number)

class MFTEntryException(MFTException):
    def __init__(self, msg, entry_number):
        '''All exceptions, at a minimum, have to have a message'''
        super().__init__(msg, entry_number)

class FixUpException(MFTException):
    def __init__(self, msg):
        pass

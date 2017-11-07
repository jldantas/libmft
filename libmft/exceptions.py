
'''
Exceptions hierachy
- MFTException
--- HeaderException
------ MFTHeaderException
------ AttrHeaderException
--- AttrContentException
--- MFTEntryException
'''

class MFTException(Exception):
    '''Base exception for all the exceptions defined by the library.'''
    def __init__(self, msg, entry_number):
        '''All exceptions, at a minimum, have to have a message and the number
        of the entry related'''
        super().__init__(msg)

        self._entry_number = entry_number

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

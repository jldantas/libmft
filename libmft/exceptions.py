class MftException(Exception):
    pass

class FixUpException(MftException):
    def __init__(self, msg):
        pass

class HeaderException(MftException):
    pass

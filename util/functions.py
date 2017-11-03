from datetime import datetime as _datetime, timedelta as _timedelta

def convert_filetime(filetime):
    '''Convert FILETIME64 to datetime object'''
    return _datetime(1601, 1, 1) + _timedelta(microseconds=(filetime/10))

def get_file_reference(file_ref):
    '''Convert a 32 bits number into the 2 bytes reference and the 6
    bytes sequence number. The return method is a tuple with the
    reference number and the sequence number, in this order.
    '''
    #TODO REALLY DEBUG/TEST THIS ARITHIMETIC!!!!!!
    return (file_ref & 0x0000ffffffffffff, (file_ref & 0xffff000000000000) >> 48)

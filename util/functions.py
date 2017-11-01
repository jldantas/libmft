from datetime import datetime as _datetime, timedelta as _timedelta

def convert_filetime(filetime):
    '''Convert FILETIME64 to datetime object'''
    return _datetime(1601, 1, 1) + _timedelta(microseconds=(filetime/10))

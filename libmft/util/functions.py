import logging
import itertools
from datetime import datetime as _datetime, timedelta as _timedelta
from collections import Iterable

from libmft.exceptions import FixUpError

MOD_LOGGER = logging.getLogger(__name__)

def convert_filetime(filetime):
    '''Convert FILETIME64 to datetime object. There is no interpretation of
    timezones. If the encoded format has a timezone, it will be returned as if
    in UTC.

    Args:
        filetime (int) - An int that represents the FILETIME value.

    Returns:
        datetime: The int converted to datetime.
    '''
    return _datetime(1601, 1, 1) + _timedelta(microseconds=(filetime/10))

def get_file_reference(file_ref):
    '''Convert a 32 bits number into the 2 bytes reference and the 6
    bytes sequence number. The return method is a tuple with the
    reference number and the sequence number, in this order.

    Args:
        file_ref (int) - An int that represents the file reference.

    Returns:
        (int, int): A tuple of two ints, where the first is the reference number
            and the second is the sequence number.
    '''
    return (file_ref & 0x0000ffffffffffff, (file_ref & 0xffff000000000000) >> 48)

def apply_fixup_array(bin_view, fx_offset, fx_count, entry_size):
    '''This function reads the fixup array and apply the correct values
    to the underlying binary stream. This function changes the bin_view
    in memory.

    Args:
        bin_view (memoryview of bytearray) - The binary stream
        fx_offset (int) - Offset to the fixup array
        fx_count (int) - Number of elements in the fixup array
        entry_size (int) - Size of the MFT entry
    '''
    fx_array = bin_view[fx_offset:fx_offset+(2 * fx_count)]
    #the array is composed of the signature + substitutions, so fix that
    fx_len = fx_count - 1
    #we can infer the sector size based on the entry size
    sector_size = int(entry_size / fx_len)
    index = 1
    position = (sector_size * index) - 2
    while (position <= entry_size):
        if bin_view[position:position+2].tobytes() == fx_array[:2].tobytes():
            #the replaced part must always match the signature!
            bin_view[position:position+2] = fx_array[index * 2:(index * 2) + 2]
        else:
            MOD_LOGGER.error("Error applying the fixup array")
            raise FixUpError(f"Applying fixup item {fx_array[:2].tobytes()} in the wrong offset {position}.")
        index += 1
        position = (sector_size * index) - 2
    MOD_LOGGER.info("Fix up array applied successfully.")

def flatten(iterable):
    '''Returns an iterable with the list flat'''
    return itertools.chain.from_iterable(a if isinstance(a,Iterable) and not isinstance(a, str) else [a] for a in iterable)

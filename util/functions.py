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

def apply_fixup_array(bin_view, fx_offset, fx_count, entry_size):
    '''This function reads the fixup array and apply the correct values
    to the underlying binary stream. This function changes the bin_view
    in memory.
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
            print("REPLACING WRONG PLACE, STOP MOTHERFUCKER!")
            #TODO error handling
        index += 1
        position = (sector_size * index) - 2

import itertools
import logging

#import libmft.api
import libmft.api
from libmft.flagsandtypes import AttrTypes, FileInfoFlags, MftUsageFlags

_MOD_LOGGER = logging.getLogger("libmft")
sh = logging.StreamHandler()
_MOD_LOGGER.addHandler(sh)
_MOD_LOGGER.setLevel(logging.WARNING)

#test = "./mft_samples/MFT_singlefile.bin"
#test = "./mft_samples/MFT_singlefileads.bin"
#test = "./mft_samples/MFT_onefiledeleted.bin"
#test = "./mft_samples/MFT_changed.bin"
#test = "./mft_samples/MFT_singlefileads.bin"

#test = "./mft_samples/MFT_twofolderonefile.bin"

#test = "./mft_samples/MFT_simplefsdeletedfolder.bin"
#test = "../full_sample.bin"

#test = "../my_mft.bin"
#test = "../data.bin"

#test = "C:/cases/full_sample.bin"
#test = "C:/cases/my_mft.bin"
#test = "C:/Users/Julio/Downloads/MFT.bin"

#------------------------------------------------------------------------------
# RECIPE 1 - Get the full path of one name of one entry
#------------------------------------------------------------------------------
def get_full_path(mft, fn_attr):
    names = [fn_attr.content.name]
    root_id = 5
    index, seq = fn_attr.content.parent_ref, fn_attr.content.parent_seq

    while index != root_id:
        try:
            entry = mft[index]

            if seq != entry.header.seq_number:
                names.append("_ORPHAN_")
                break
            else:
                parent_fn_attr = entry.get_main_filename_attr()
                index, seq = parent_fn_attr.content.parent_ref, parent_fn_attr.content.parent_seq
                names.append(parent_fn_attr.content.name)
        except ValueError as e:
            names.append("_ORPHAN_")
            break

    return "\\".join(reversed(names))

def stress_filename(mft_config):
    sample = "./mft_samples/stress_filename.bin"

    with open(sample, "rb") as mft_file:
        mft = libmft.api.MFT.load_from_file_pointer(mft_file, mft_config)

    print("MFT length:", len(mft))
    for entry_n in mft:
        print(entry_n, mft[entry_n].is_directory(), mft.get_full_path(entry_n), mft[entry_n].get_names(), mft[entry_n].get_datastream_names())

def stress_ads(mft_config):
    sample = "./mft_samples/MFT_singlefileads.bin"

    with open(sample, "rb") as mft_file:
        mft = libmft.api.MFT(mft_file, mft_config)

    print("MFT length:", len(mft))
    for entry_n in mft:
        print(entry_n, mft.get_full_path(entry_n), mft[entry_n].get_names(), mft[entry_n].get_datastream_names())

def test_my_mft():
    test = "../../MFT_C.bin"
    #test = "../../my_mft.bin"
    #test = "c:/cases/my_mft.bin"
    mft_config = libmft.api.MFTConfig()
    mft_config.load_dataruns = False
    mft_config.load_object_id = False
    mft_config.load_sec_desc = False
    mft_config.load_idx_root = False
    mft_config.load_idx_alloc = False
    mft_config.load_bitmap = False
    mft_config.load_reparse = False
    mft_config.load_ea_info = False
    mft_config.load_ea = False
    mft_config.load_log_tool_str = False
    mft_config.load_attr_list = False

    '''Entries to play:
        my_mft/75429 - datastream (multiple data attributes accross many entries)
        my_mft/4584 - filenames (multiple hardlinks)
        my_mft/5213 - filenames (multiple names one entry)
    '''


    with open(test, "rb") as mft_file:
        #mft = libmft.api.MFT(mft_file)
        mft = libmft.api.MFT(mft_file, mft_config)
        #print(mft[75429])
        #test_1(mft)
        for entry in mft:
            pass

def test_botched_header():
    test = "../data.bin"
    mft_config = copy.deepcopy(libmft.api.MFT.mft_config)
    mft_config["entry_size"] = 1024
    mft_config["ignore_signature_check"] = True

    with open(test, "rb") as mft_file:
        mft = libmft.api.MFT(mft_file, mft_config)
        for i in mft:
            print(i)

def main():
    test_my_mft()





if __name__ == '__main__':
    main()

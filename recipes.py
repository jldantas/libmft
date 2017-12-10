import copy
import itertools

#import libmft.api
import libmft.api
from libmft.flagsandtypes import AttrTypes, FileInfoFlags, MftUsageFlags

#test = "./mft_samples/MFT_singlefile.bin"
#test = "./mft_samples/MFT_singlefileads.bin"
#test = "./mft_samples/MFT_onefiledeleted.bin"
#test = "./mft_samples/MFT_changed.bin"
#test = "./mft_samples/MFT_singlefileads.bin"

#test = "./mft_samples/MFT_twofolderonefile.bin"

#test = "./mft_samples/MFT_simplefsdeletedfolder.bin"
#test = "../full_sample.bin"

test = "../my_mft.bin"

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

#------------------------------------------------------------------------------
# RECIPE 2 - Get
#------------------------------------------------------------------------------
def test_1(mft):
    entry_n = 4584

    fn_attrs = mft[entry_n].get_unique_filename_attrs()
    main_ds = mft[entry_n].get_datastream()
    for fn in fn_attrs:
        print(get_full_path(mft, fn), fn, main_ds)



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

def test_data(mft_config):
    sample = "multiple_data.bin"
    mft_config["apply_fixup_array"] = False
    mft_config["load_dataruns"] = False

    with open(sample, "rb") as mft_file:
        mft = libmft.api.MFT.load_from_file_pointer(mft_file, mft_config)

    for entry_n in mft:
        print(entry_n, mft[entry_n])
        print(mft[entry_n].data_streams)


def main():
    #mft_config = copy.deepcopy(libmft.api.MFT.mft_config)
    mft_config = copy.deepcopy(libmft.api.MFT.mft_config)
    mft_config["attributes"]["load_dataruns"] = False
    mft_config["attributes"]["object_id"] = False
    mft_config["attributes"]["sec_desc"] = False
    mft_config["attributes"]["idx_root"] = False
    mft_config["attributes"]["idx_alloc"] = False
    mft_config["attributes"]["bitmap"] = False
    mft_config["attributes"]["reparse"] = False
    mft_config["attributes"]["ea_info"] = False
    mft_config["attributes"]["ea"] = False
    mft_config["attributes"]["log_tool_str"] = False
    mft_config["attributes"]["attr_list"] = False
    # mft_config["datastreams"] = {"enable" : True,
    #                              "load_content" : True


    #stress_filename(mft_config)
    #stress_ads(mft_config)
    #test_data(mft_config)

    '''Entries to play:
        my_mft/75429 - datastream (multiple data attributes accross many entries)
        my_mft/4584 - filenames (multiple hardlinks)
        my_mft/5213 - filenames (multiple names one entry)
    '''


    with open(test, "rb") as mft_file:
        mft = libmft.api.MFT(mft_file, mft_config)

        for entry in mft:
            #print(entry)
            b = entry.get_unique_filename_attrs()
            if b is not None:
                for a in b:
                    get_full_path(mft, a)
                    

        # print(len(mft))
        #
        # for a in mft[4584].get_unique_filename_attrs():
        #     print(get_full_path(mft, a))
        # #print(mft[4584].get_attributes(AttrTypes.FILE_NAME))
        #
        # for a in mft[5213].get_unique_filename_attrs():
        #     print(a)
        #
        # print(mft[4584])
        #
        # test_1(mft)


        # for a in mft:
        #     pass


    # with open(test, "rb") as mft_file:
    #     #mft = libmft.api.MFT.load_from_file_pointer(mft_file, mft_config)
    #     mft = libmft.api.MFT.load_from_file_pointer(mft_file)
    #
    # #print(mft[4584], "\n", mft[149327], "\n", mft[8277], "\n", mft[8278])
    #
    # #print(get_names_from_fn(mft[4584]), get_names_from_fn(mft[64485]))
    # # print(get_full_path_v2(mft, 4584), get_full_path_v2(mft, 64485))
    # # print(mft[4584], mft[64485])
    #
    # print(mft[75429])
    # print(mft[75429].data_streams)

    #print(mft[5213])

    # for n, entry in mft.items():
    #     a = entry.get_attributes(AttrTypes.DATA)
    #     if a is not None and len(a) >= 5:
    #         print(n, a)
    #         break

    #
            #break

    #
    # stats = {}
    # for i, entry in enumerate(mft):
    #     if entry is not None:
    #         for key, l in entry.attrs.items():
    #             if key.name not in stats:
    #                 stats[key.name] = 0
    #             stats[key.name] += len(l)
    #
    # print(stats)


if __name__ == '__main__':
    main()

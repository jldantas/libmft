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

#------------------------------------------------------------------------------
# RECIPE 2 - Get
#------------------------------------------------------------------------------
def pretty_print(data):
    print("--------------------------------")
    print("is_deleted:", data["is_deleted"], "\tis_directory:", data["is_directory"])
    print("path:", data["path"])
    print("size:", data["size"], "allocated size:", data["alloc_size"])
    print("**STD_TIMES**")
    print("\tcreated:", data["std_created"], "\tchanged:", data["std_changed"])
    print("\tmft_change:", data["std_mft_change"], "\taccessed:", data["std_accessed"])
    print("**FN_TIMES**")
    print("\tcreated:", data["fn_created"], "\tchanged:", data["fn_changed"])
    print("\tmft_change:", data["fn_mft_change"], "\taccessed:", data["fn_accessed"])

def build_info_entry(mft, entry, std_info, fn_attr, ds):
    data = {}
    data["is_deleted"] = entry.is_deleted()
    data["is_directory"] = entry.is_directory()
    data["std_created"] = std_info.content.get_created_time()
    data["std_changed"] = std_info.content.get_changed_time()
    data["std_mft_change"] = std_info.content.get_mftchange_time()
    data["std_accessed"] = std_info.content.get_accessed_time()
    data["fn_created"] = fn_attr.content.get_created_time()
    data["fn_changed"] = fn_attr.content.get_changed_time()
    data["fn_mft_change"] = fn_attr.content.get_mftchange_time()
    data["fn_accessed"] = fn_attr.content.get_accessed_time()
    if ds.name is None:
        data["path"] = get_full_path(mft, fn_attr)
    else:
        data["path"] = ":".join((get_full_path(mft, fn_attr), ds.name))
    data["size"] = ds.size
    data["alloc_size"] = ds.alloc_size

    return data

def test_1(mft):
    entry_n = 75429

    #entry = mft[entry_n]
    for entry in mft:
        std_info = entry.get_attributes(AttrTypes.STANDARD_INFORMATION)[0]
        fn_attrs = entry.get_unique_filename_attrs()
        main_fn = entry.get_main_filename_attr()
        ds_names = entry.get_datastream_names()
        if ds_names is not None:
            if None in ds_names:
                main_ds = entry.get_datastream()
            else:
                main_ds = None
        else:
            main_ds = None
        for ds_name in ds_names:
            pretty_print(build_info_entry(mft, entry, std_info, main_fn, entry.get_datastream(ds_name)))
        for fn in fn_attrs:
            if fn.content.parent_ref != main_fn.content.parent_ref:
                pretty_print(build_info_entry(mft, entry, std_info, fn, main_ds))


    # fn_attrs = mft[entry_n].get_unique_filename_attrs()
    # main_ds = mft[entry_n].get_datastream()
    # for fn in fn_attrs:
    #     print(get_full_path(mft, fn), fn, main_ds)

    entry_n = 4584
    entry_n = 75429
    print(mft[entry_n].get_main_filename_attr())
    print(mft[entry_n].get_datastream_names())


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
    test = "../my_mft.bin"
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

    '''Entries to play:
        my_mft/75429 - datastream (multiple data attributes accross many entries)
        my_mft/4584 - filenames (multiple hardlinks)
        my_mft/5213 - filenames (multiple names one entry)
    '''


    with open(test, "rb") as mft_file:
        mft = libmft.api.MFT(mft_file, mft_config)
        test_1(mft)
        # for entry in mft:
        #     #print(entry)
        #     b = entry.get_unique_filename_attrs()
        #     if b is not None:
        #         for a in b:
        #             get_full_path(mft, a)

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

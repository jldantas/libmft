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
    print("path:", data["path"])
    print("readonly:", data["readonly"], "\thidden:", data["hidden"], "\tsystem:", data["system"], "\tencrypted:", data["encrypted"])
    print("is_deleted:", data["is_deleted"], "\tis_directory:", data["is_directory"], "\tis_ads:", data["is_ads"])
    print("entry_n:", data["entry_n"], "\tsize:", data["size"], "\tallocated size:", data["alloc_size"])
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
    data["entry_n"] = entry.header.mft_record
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
        data["is_ads"] = False
    else:
        data["path"] = ":".join((get_full_path(mft, fn_attr), ds.name))
        data["is_ads"] = True
    data["size"] = ds.size
    data["alloc_size"] = ds.alloc_size

    data["readonly"] = True if std_info.content.flags & libmft.flagsandtypes.FileInfoFlags.READ_ONLY else False
    data["hidden"] = True if std_info.content.flags & libmft.flagsandtypes.FileInfoFlags.HIDDEN else False
    data["system"] = True if std_info.content.flags & libmft.flagsandtypes.FileInfoFlags.SYSTEM else False
    data["encrypted"] = True if std_info.content.flags & libmft.flagsandtypes.FileInfoFlags.ENCRYPTED else False

    return data

def test_1(mft):
    entry_n = 75429

    #entry = mft[entry_n]
    default_stream = libmft.api.Datastream()
    fake_time = libmft.util.functions.convert_filetime(0)
    default_filename = libmft.api.Attribute(None, libmft.attrcontent.FileName((5, mft[5].header.seq_number, fake_time, fake_time, fake_time, fake_time, libmft.flagsandtypes.FileInfoFlags(0), -1, 0, libmft.flagsandtypes.NameType.POSIX, "INVALID")))
    for entry in mft:
        #print(entry)

        #sometimes entries have no attributes and are marked as deleted, there is no information there
        if not entry.attrs and not entry.header.usage_flags:
            continue
        #other times, we might have a partial entry (entry that has been deleted,
        #but occupied more than one entry) and not have the basic attribute information
        #like STANDARD_INFORMATION or FILENAME, in these cases, ignore as well
        if not entry.header.usage_flags & libmft.flagsandtypes.MftUsageFlags.IN_USE and entry.get_attributes(AttrTypes.STANDARD_INFORMATION) is None:
            continue

        main_ds = default_stream
        std_info = entry.get_attributes(AttrTypes.STANDARD_INFORMATION)[0]
        fn_attrs = entry.get_unique_filename_attrs()
        main_fn = entry.get_main_filename_attr()
        if not fn_attrs:
            fn_attrs = [default_filename]
            main_fn = default_filename
        ds_names = entry.get_datastream_names()
        if ds_names is not None:
            for ds_name in ds_names:
                pretty_print(build_info_entry(mft, entry, std_info, main_fn, entry.get_datastream(ds_name)))
            if None in ds_names:
                main_ds = entry.get_datastream()
        else:
            pretty_print(build_info_entry(mft, entry, std_info, main_fn, default_stream))

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
    #test = "../my_mft.bin"
    test = "c:/cases/my_mft.bin"
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
        mft = libmft.api.MFT(mft_file)
        #print(mft[274357])
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

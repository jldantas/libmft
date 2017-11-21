import copy
import itertools

import libmft.api
from libmft.flagsandtypes import AttrTypes, FileInfoFlags

#test = "./mft_samples/MFT_singlefile.bin"
#test = "./mft_samples/MFT_singlefileads.bin"
#test = "./mft_samples/MFT_onefiledeleted.bin"
#test = "./mft_samples/MFT_changed.bin"
#test = "./mft_samples/MFT_singlefileads.bin"

#test = "./mft_samples/MFT_twofolderonefile.bin"

#test = "./mft_samples/MFT_simplefsdeletedfolder.bin"
#test = "../full_sample.bin"

#test = "../my_mft.bin"

#test = "C:/cases/full_sample.bin"
test = "C:/cases/my_mft.bin"
#test = "C:/Users/Julio/Downloads/MFT.bin"

def get_relevant_fields(mft, entry, string_format="%Y-%m-%d %H:%M:%S"):
    info = []
    print(entry)
    std_info = entry.get_attributes(AttrTypes.STANDARD_INFORMATION)[0].content
    full_path = mft.get_full_path(entry.header.mft_record)

    entry_info = [str(entry.header.mft_record), str(entry.is_deleted()), str(entry.is_directory())]
    flags_info = ["True" if std_info.flags & FileInfoFlags.READ_ONLY else "False",
                  "True" if std_info.flags & FileInfoFlags.HIDDEN else "False",
                  "True" if std_info.flags & FileInfoFlags.SYSTEM else "False",
                  "True" if std_info.flags & FileInfoFlags.SPARSE_FILE else "False",
                  "True" if std_info.flags & FileInfoFlags.ENCRYPTED else "False"]
    times_info = [std_info.get_created_time().strftime(string_format),
                  std_info.get_changed_time().strftime(string_format),
                  std_info.get_mftchange_time().strftime(string_format),
                  std_info.get_accessed_time().strftime(string_format)]

    try:
        fn = entry.get_attributes(AttrTypes.FILE_NAME)[0].content
        fn_info = [fn.get_created_time().strftime(string_format),
                   fn.get_changed_time().strftime(string_format),
                   fn.get_mftchange_time().strftime(string_format),
                   fn.get_accessed_time().strftime(string_format)]
    except TypeError as e:
        fn = None
        fn_info = ["**INVALID**"] * 4

    data_streams = entry.get_datastream_names()
    if data_streams is not None:
        for stream in data_streams:
            if stream is None:
                data_info = ["False", full_path]
            else:
                data_info = ["True", f"{full_path}:{stream}"]
            data_info.append(str(entry.get_data_size(stream)))
            info.append([entry_info, flags_info, times_info, fn_info, data_info])
    else:
        if fn is not None:
            data_info = ["False", fn.name, "**INVALID**"]
        else:
            data_info = ["False", "**INVALID**", "**INVALID**"]
        info.append([entry_info, flags_info, times_info, fn_info, data_info])

    #print(entry_info, flags_info, times_info, fn_info)

    return info


def stress_filename(mft_config):
    sample = "./mft_samples/stress_filename.bin"

    with open(sample, "rb") as mft_file:
        mft = libmft.api.MFT(mft_file, mft_config)

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


def main():
    mft_config = copy.deepcopy(libmft.api.MFT.mft_config)
    mft_config["load_attr_list"] = False
    mft_config["load_oject_id"] = False
    mft_config["load_sec_desc"] = False
    mft_config["load_idx_root"] = False
    mft_config["load_idx_alloc"] = False
    mft_config["load_bitmap"] = False
    mft_config["load_reparse"] = False
    mft_config["load_ea_info"] = False
    mft_config["load_ea"] = False
    mft_config["load_log_tool_str"] = False

    #stress_filename(mft_config)
    #stress_ads(mft_config)


    with open(test, "rb") as mft_file:
        mft = libmft.api.MFT(mft_file, mft_config)

    for entry_n in mft:
        for line in get_relevant_fields(mft, mft[entry_n]):
            pass
            #print(",".join(itertools.chain.from_iterable(line)))
        #print(get_relevant_fields(mft, mft[entry_n]))
        #print(entry_n, mft.get_full_path(entry_n), mft[entry_n].get_names(), mft[entry_n].get_datastream_names())
    #     mft = libmft.api.MFT(mft_file)
    #
    #
    #
    #
    # for entry_n in mft:
    #     #if mft[entry_n].has_ads() and len(mft[entry_n].get_attributes(AttrTypes.DATA)) >= 3:
    #     #print(entry_n)
        # print(entry_n, mft[entry_n].is_directory(), mft.get_full_path(entry_n), mft[entry_n].get_names(), mft[entry_n].get_datastream_names())
    #     #print(entry_n,  mft[entry_n])
    #     #print(mft[entry_n].has_ads())

    #print(mft[39].get_attributes(AttrTypes.DATA))

    #mft.get_full_path(38941)

    #print(mft.get_full_path(15173))

    # for i, entry in enumerate(mft):
    #     #if entry is not None and entry.is_deleted():
    #     if entry is not None:
    #         #mft._find_base_entry(i)
    #         print(i, entry.is_deleted(), mft.get_full_path(i))

    # i = 98126
    # print(i, mft[i].is_deleted(), mft.get_full_path(i))
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



    # print(mft[39])
    # print()
    # print(mft[41])

    # a = [92924, 5123, 5126, 4999, 5000, 5128, 5072, 5074, 5077, 5079, 5210, 5211, 5212, 5091, 228, 5092, 5098, 5106, 5111, 5114, 5115, 95486]
    # for b in a:
    #     print(mft[b])

    # print(mft[166300])
    # print()
    # print(mft[165669])

    # print(mft[213989])
    # print()
    # print(mft[171977])
    # print()
    # print(mft[274357])

            # for attr in entry.attrs.values():
            #     for a in attr:
            #         if a.is_non_resident():
            #             print(a)


    #print(mft._find_base_entry(116004))
    # a = []
    # b = []
    # for i, entry in enumerate(mft):
    #     if entry is not None:
    #         j = mft._find_base_entry(i)
    #         if j != i:
    #             a.append(i)
    #             b.append(j)
    #
    # a = set(a)
    # b = set(b)
    # for e in a:
    #     print(mft[e])
    # for e in b:
    #     print(mft[e])


    #print(mft[115975].get_file_size())
    # for i, entry in enumerate(mft):
    #     print(i, entry)
    #     if entry is not None:
    #         #print(i, entry)
    #         #print(mft.get_full_path(i))
    #         #print(entry.get_standard_info())
    #         #print(entry.header.base_record_ref)
    #         #if (entry.header.base_record_ref):
    #         #    print(i)
    #         j = mft._find_base_entry(i)
    #         if i != j:
    #             print(i, j)
    #         #print("del?", entry.is_deleted(), "- sizes:", entry.get_full_path(i))
    #         pass
        #print(i, entry)
    #print(mft[8])

    #print(mft.entries)
    #print(mft.entries)
    # for i in range(0, len(mft)):
    #     try:
    #         print(mft.get_entry(i).get_file_size(), mft.get_entry(i).get_full_path)
    #     except AttributeError:
    #         print("Empty entry")

main()

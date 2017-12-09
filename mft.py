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

def get_info_data_stream(entry, data_stream):
    info = {}

def get_names_from_fn(entry):
    fn_attrs = entry.get_attributes(AttrTypes.FILE_NAME)
    control = None

    if fn_attrs is not None:
        control = {}
        for fn in fn_attrs:
            temp = (fn.content.parent_ref, fn.content.parent_seq)
            if temp not in control:
                control[temp] = fn.content.name
            else:
                if len(control[temp]) < len(fn.content.name):
                    control[temp] = fn.content.name

    return control

def get_fn_nametype_value(attr_fn):
    return attr_fn.content.name_type.value

def get_full_path_fn(mft, parent_ref, parent_seq, name):
    names = [name]
    root_id = 5
    index, seq = parent_ref, parent_seq

    while index != root_id:
        entry = mft[index]

        if seq != entry.header.seq_number:
            names.append("_ORPHAN_")
            break
        else:
            fn_attrs = entry.get_attributes(AttrTypes.FILE_NAME)

            if fn_attrs is not None:
                fn_attrs.sort(key=get_fn_nametype_value)
                content = fn_attrs[0].content
                index, seq = content.parent_ref, content.parent_seq
                names.append(content.name)

    return "\\".join(reversed(names))

def get_full_path_v2(mft, entry_number):
    names = {}

    if mft[entry_number] is None:
        return None

    name_parents = get_names_from_fn(mft[entry_number])
    for (parent_ref, parent_seq), name in name_parents.items():
        names[(parent_ref, parent_seq)] = get_full_path_fn(mft, parent_ref, parent_seq, name)

    return names

# def get_relevant_fields(mft, entry, string_format="%Y-%m-%d %H:%M:%S"):
#     info = []
#     std_info = entry.get_attributes(AttrTypes.STANDARD_INFORMATION)[0].content
#     full_path = mft.get_full_path(entry.header.mft_record)
#
#     entry_info = [str(entry.header.mft_record), str(entry.is_deleted()), str(entry.is_directory())]
#     flags_info = ["True" if std_info.flags & FileInfoFlags.READ_ONLY else "False",
#                   "True" if std_info.flags & FileInfoFlags.HIDDEN else "False",
#                   "True" if std_info.flags & FileInfoFlags.SYSTEM else "False",
#                   "True" if std_info.flags & FileInfoFlags.SPARSE_FILE else "False",
#                   "True" if std_info.flags & FileInfoFlags.ENCRYPTED else "False"]
#     times_info = [std_info.get_created_time().strftime(string_format),
#                   std_info.get_changed_time().strftime(string_format),
#                   std_info.get_mftchange_time().strftime(string_format),
#                   std_info.get_accessed_time().strftime(string_format)]
#
#     try:
#         fn = entry.get_attributes(AttrTypes.FILE_NAME)[0].content
#         fn_info = [fn.get_created_time().strftime(string_format),
#                    fn.get_changed_time().strftime(string_format),
#                    fn.get_mftchange_time().strftime(string_format),
#                    fn.get_accessed_time().strftime(string_format)]
#     except TypeError as e:
#         fn = None
#         fn_info = ["**INVALID**"] * 4
#
#     data_streams = entry.get_datastream_names()
#     if data_streams is not None:
#         for stream in data_streams:
#             if stream is None:
#                 data_info = ["False", full_path]
#             else:
#                 data_info = ["True", f"{full_path}:{stream}"]
#             data_info.append(str(entry.get_data_size(stream)))
#             info.append([entry_info, flags_info, times_info, fn_info, data_info])
#     else:
#         if fn is not None:
#             data_info = ["False", fn.name, "**INVALID**"]
#         else:
#             data_info = ["False", "**INVALID**", "**INVALID**"]
#         info.append([entry_info, flags_info, times_info, fn_info, data_info])
#
#     #print(entry_info, flags_info, times_info, fn_info)
#
#     return info

def get_relevant_static_fields(mft, entry, string_format="%Y-%m-%d %H:%M:%S"):
    std_info = entry.get_attributes(AttrTypes.STANDARD_INFORMATION)[0].content

    s_fields = {"mft_record" : str(entry.header.mft_record),
                "is_deleted" : str(entry.is_deleted()),
                "is_directory" : str(entry.is_directory()),
                "is_read_only" : "True" if std_info.flags & FileInfoFlags.READ_ONLY else "False",
                "is_hidden" : "True" if std_info.flags & FileInfoFlags.HIDDEN else "False",
                "is_system" : "True" if std_info.flags & FileInfoFlags.SYSTEM else "False",
                "is_sparse" : "True" if std_info.flags & FileInfoFlags.SPARSE_FILE else "False",
                "is_encrypted" : "True" if std_info.flags & FileInfoFlags.ENCRYPTED else "False",
                "std_created_time" : std_info.get_created_time().strftime(string_format),
                "std_changed_time" : std_info.get_changed_time().strftime(string_format),
                "std_mft_change_time" : std_info.get_mftchange_time().strftime(string_format),
                "std_accessed_time" : std_info.get_accessed_time().strftime(string_format)}

    return s_fields

def get_relevant_fields_v2(mft, entry, string_format="%Y-%m-%d %H:%M:%S"):
    static = get_relevant_static_fields(mft, entry, string_format)

    # fns = get_names_from_fn(entry)
    # if is not None:
    #     dynamic = {}
    # else:
    #     dynamic = {}

    try:
        fn = entry.get_attributes(AttrTypes.FILE_NAME)[0].content
        fn_info = [fn.get_created_time().strftime(string_format),
                   fn.get_changed_time().strftime(string_format),
                   fn.get_mftchange_time().strftime(string_format),
                   fn.get_accessed_time().strftime(string_format)]
    except TypeError as e:
        fn = None
        fn_info = ["**INVALID**"] * 4


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


    with open(test, "rb") as mft_file:
        mft = libmft.api.MFT(mft_file, mft_config)

        print(len(mft))
        a = mft[75429]
        for stream in a.data_streams:
            if not stream.is_resident():
                stream.get_dataruns()
        print(mft[75429])

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

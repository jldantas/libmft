import libmft.api

#test = "./mft_samples/MFT_singlefile.bin"
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

def main():
    with open(test, "rb") as mft_file:
        mft = libmft.api.MFT(mft_file)

    print(len(mft))
    #mft.get_full_path(38941)

    #print(mft.get_full_path(15173))

    # for i, entry in enumerate(mft):
    #     #if entry is not None and entry.is_deleted():
    #     if entry is not None:
    #         #mft._find_base_entry(i)
    #         print(i, entry.is_deleted(), mft.get_full_path(i))

    i = 98126
    print(i, mft[i].is_deleted(), mft.get_full_path(i))

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

import libmft.data

test = "./mft_samples/MFT_singlefile.bin"
#test = "./mft_samples/MFT_onefiledeleted.bin"
#test = "./mft_samples/MFT_singlefileads.bin"
#test = "./mft_samples/MFT_twofolderonefile.bin"
#test = "C:/cases/full_sample.bin"
#test = "C:/cases/my_mft.bin"
#test = "C:/Users/Julio/Downloads/MFT.bin"

def main():
    with open(test, "rb") as mft_file:
        mft = libmft.data.MFT(mft_file)

    print(len(mft))
    #print(mft[115975].get_file_size())
    for i, entry in enumerate(mft):
        if entry is not None:
            #print(i, entry)
            #print(mft.get_full_path(i))
            #print(entry.get_standard_info())
            print("del?", entry.is_deleted(), "- sizes:", entry.get_file_size())
            pass
        #print(i, entry)
    print(mft[8])

    #print(mft.entries)
    # for i in range(0, len(mft)):
    #     try:
    #         print(mft.get_entry(i).get_file_size(), mft.get_entry(i).get_full_path)
    #     except AttributeError:
    #         print("Empty entry")

main()

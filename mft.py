import mftres.data

test = "./mft_samples/MFT_singlefile.bin"
#test = "./mft_samples/MFT_singlefileads.bin"
#test = "./mft_samples/MFT_twofolderonefile.bin"
#test = "C:/cases/full_sample.bin"
#test = "C:/cases/my_mft.bin"
test = "C:/Users/Julio/Downloads/MFT.bin"

def main():
    sizes = [1024, 4096, 512, 2048]
    sigs = [b"FILE", b"BAAD", b"INDX"]

    with open(test, "rb") as mft_file:
        mftres.data.MFT(mft_file)

main()

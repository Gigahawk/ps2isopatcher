from ps2isopatcher.iso import Ps2Iso, TreeObject, TreeFolder, TreeFile

def print_tree(item: TreeObject, level=0):
    name = item.name
    spacing = " "*(level*2)
    print(f"{spacing}{name}")
    if isinstance(item, TreeFolder):
        for c in item.children:
            print_tree(c, level=level+1)

def print_tree_flat(item: TreeObject):
    path = item.path
    print(path)
    if isinstance(item, TreeFolder):
        for c in item.children:
            print_tree_flat(c)


def main():
    f_name = "mm.iso"
    iso = Ps2Iso(f_name, mutable=False)
    print_tree(iso.tree)
    print_tree_flat(iso.tree)
    path = "/PDATA/DATA0.BIN;1"
    obj: TreeFile= iso.get_object(path)
    print(f"{path} is at lba {obj.lba}")
    print(f"start: {hex(obj.lba*iso.block_size)}")
    print(f"end: {hex(obj.lba*iso.block_size + obj.size)}")
    print(f"size: {obj.size}")
    print(f"{path} has {iso.get_blocks_allocated(path)} blocks allocated")
    print(f"Exporting {path}")
    obj.export(".export")
    data = obj.data

    print(f"Appending {path} with a buncha B0 00 00 B5")
    data += bytes([0xB0, 0x00, 0x00, 0xB5]*1000)

    #print("Removing last entry from index, hopefully it's not that important")
    #data = data[:-12]

    replacements = [(path, data)]
    iso.replace_files(replacements, allow_move=True)
    print(f"Writing to out.iso")
    iso.write("out.iso")


if __name__ == "__main__":
    main()



from bitstring import Bits
from ps2isopatcher.iso import Ps2Iso, TreeObject, TreeFolder

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
    path = "/RAW/IOPRP310.IMG;1"
    print(iso.get_object(path))
    print(iso.get_object(path).name)
    print(iso.get_object(path).lba)
    print(f"{path} has {iso.get_blocks_allocated(path)} blocks allocated")
    replacements = [(path, Bits(filename="test.txt"))]
    print(f"Replacing {path} with test.txt")
    import pdb
    pdb.set_trace()
    iso.replace_files(replacements)
    print(f"Writing to out.iso")
    import pdb
    pdb.set_trace()
    iso.write("out.iso")


if __name__ == "__main__":
    main()



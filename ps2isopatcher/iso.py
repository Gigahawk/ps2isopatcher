# https://wiki.osdev.org/ISO_9660
import os
import logging
from math import ceil

from bitstring import BitArray, Bits

from ps2isopatcher.util import FileBytes


# Primary Volume Descriptor
class PVD:
    PVD_OFFSET = 0x10*2048  # PVD starts after System Area
    PVD_LENGTH = 2048
    SYST_ID_OFFSET = 8
    SYST_ID_LENGTH = 32
    BLOCK_SIZE_OFFSET = 128
    BLOCK_SIZE_LENGTH = 2
    PATH_TABLE_SIZE_OFFSET = 132
    PATH_TABLE_SIZE_LENGTH = 4
    L_PATH_TABLE_OFFSET = 140
    L_PATH_TABLE_OPT_OFFSET = 144
    M_PATH_TABLE_OFFSET = 148
    M_PATH_TABLE_OPT_OFFSET = 152
    PATH_TABLE_LENGTH = 4

    def __init__(self, data: bytes):
        self.data = data[
            self.PVD_OFFSET:(self.PVD_OFFSET+self.PVD_LENGTH)
        ]

    @property
    def system_identifier(self):
        return self._get_str(
            self.SYST_ID_OFFSET, self.SYST_ID_LENGTH)

    @property
    def logical_block_size(self):
        return self._get_intle(
            self.BLOCK_SIZE_OFFSET, self.BLOCK_SIZE_LENGTH)

    @property
    def path_table_size(self):
        return self._get_intle(
            self.PATH_TABLE_SIZE_OFFSET, self.PATH_TABLE_SIZE_LENGTH)

    @property
    def l_path_table(self):
        return self._get_intle(
            self.L_PATH_TABLE_OFFSET, self.PATH_TABLE_LENGTH)
    @property
    def l_path_table_opt(self):
        return self._get_intle(
            self.L_PATH_TABLE_OPT_OFFSET, self.PATH_TABLE_LENGTH)

    @property
    def m_path_table(self):
        return self._get_intle(
            self.M_PATH_TABLE_OFFSET, self.PATH_TABLE_LENGTH)

    @property
    def m_path_table_opt(self):
        return self._get_intle(
            self.M_PATH_TABLE_OPT_OFFSET, self.PATH_TABLE_LENGTH)

    def _get_intle(self, offset: int, length: int) -> int:
        e = self._get_entry(offset, length)
        return int.from_bytes(e, byteorder="little", signed=True)

    def _get_intbe(self, offset: int, length: int) -> int:
        e = self._get_entry(offset, length)
        return int.from_bytes(e, byteorder="big", signed=True)

    def _get_str(self, offset: int, length: int) -> str:
        e = self._get_entry(offset, length)
        return e.decode().strip()

    def _get_entry(self, offset: int, length: int) -> bytes:
        return self.data[offset:(offset+length)]

class PathTable:
    def __init__(self, data: bytes, addr: int, size: int):
        self.data = data
        self.tbl_data = self.data[addr:(addr+size)]

    def get_entries(self):
        paths = []

        i = 0
        dir_id = 1
        while i < len(self.tbl_data):
            name_len = int.from_bytes(self.tbl_data[i:(i+1)])
            total_len = name_len + 8
            if name_len % 2:
                total_len += 1
            entry = self.tbl_data[i:(i+total_len)]
            lba = self._get_lba(entry)
            parent_dir_id = self._get_parent_dir_id(entry)
            name = self._get_name(entry, name_len)
            paths.append({
                "name": name,
                "lba": lba,
                "parent_dir_id": parent_dir_id,
                "dir_id": dir_id
            })
            i += total_len
            dir_id += 1
        return paths

    def _get_name(self, entry: bytes, length: int) -> str:
        return entry[8:(8+length)].decode().strip()

    def _get_lba(self, entry: bytes):
        pass

    def _get_parent_dir_id(self, entry: bytes):
        pass


class LPathTable(PathTable):
    def _get_lba(self, entry):
        return int.from_bytes(entry[2:6], byteorder="little")

    def _get_parent_dir_id(self, entry):
        return int.from_bytes(entry[6:8], byteorder="little")

class PathTables:
    def __init__(self, data: bytes, pvd: PVD):
        self.data = data
        size = pvd.path_table_size
        lpt_addr = pvd.l_path_table*2048
        self.l_path_table = LPathTable(self.data, lpt_addr, size)

    def get_path_tree(self) -> "TreeFolder":
        paths = self.l_path_table.get_entries()
        root = paths.pop(0)
        return TreeFolder(root, children=paths, data=self.data)

class DirTable:
    def __init__(self, data: bytes, lba: int, block_size: int):
        self.dt_addr = lba*block_size
        self.dt_size = block_size
        self.data = data
        self.set_tbl_data()

    def get_entries(self):
        entries = []

        i = 0
        while True:
            total_len = int.from_bytes(self.tbl_data[i:(i+1)])
            if total_len == 0:
                break
            entry = self.tbl_data[i:(i+total_len)]
            lba = self._get_lba(entry)
            size = self._get_size(entry)
            name_len = self._get_name_length(entry)
            name = self._get_name(entry, name_len)
            entries.append({
                "name": name,
                "size": size,
                "lba": lba,
            })
            i += total_len
        return entries

    def set_entry(self, name: str, lba: int, size: int):
        i = 0
        print(f"Searching for {name}")
        while True:
            total_len = int.from_bytes(self.tbl_data[i:(i+1)])
            if total_len == 0:
                break
            offset = i
            entry = self.tbl_data[offset:(i+total_len)]
            name_len = self._get_name_length(entry)
            n = self._get_name(entry, name_len)
            print(n)
            import pdb;pdb.set_trace()
            if n == name:
                iso_offset = offset + self.dt_addr
                lba_offset = iso_offset + 2*8
                size_offset = iso_offset + 10*8
                lba_le = Bits(uintle=lba, length=4*8)
                lba_be = Bits(uintbe=lba, length=4*8)
                lba_bits = BitArray()
                lba_bits.append(lba_le)
                lba_bits.append(lba_be)
                size_le = Bits(uintle=size, length=4*8)
                size_be = Bits(uintbe=size, length=4*8)
                size_bits = BitArray()
                size_bits.append(size_le)
                size_bits.append(size_be)
                self.data.overwrite(lba_bits, lba_offset)
                self.data.overwrite(size_bits, size_offset)
                self.set_tbl_data()
                break
            i += total_len

    def set_tbl_data(self):
        self.tbl_data = self.data[self.dt_addr:(self.dt_addr+self.dt_size)]

    def _get_lba(self, entry) -> int:
        return int.from_bytes(entry[2:6], byteorder="little")

    def _get_size(self, entry) -> int:
        return int.from_bytes(entry[10:14], byteorder="little")

    def _get_name_length(self, entry) -> int:
        return int.from_bytes(entry[32:33], byteorder="little")

    def _get_name(self, entry, length) -> str:
        return entry[33:(33+length)].decode().strip()


class TreeObject:
    def __init__(self, info, parent=None):
        self.__name = info["name"]
        self.__lba = info["lba"]
        self.__parent = parent

    @property
    def parent(self):
        return self.__parent

    @property
    def name(self):
        return self.__name

    @property
    def lba(self):
        return self.__lba

    @property
    def path(self):
        if self.parent is None:
            return ""
        return f"{self.parent.path}/{self.name}"

    def update_toc(self, lba, size):
        self.parent._dirtable.set_entry(self.name, lba, size)

class TreeFile(TreeObject):
    def __init__(self, info, parent=None):
        super().__init__(info, parent=parent)
        self.__size = info["size"]

    @property
    def size(self):
        return self.__size

class TreeFolder(TreeObject):
    def __init__(
            self, info, parent=None, children=None, data=None, block_size=2048):
        super().__init__(info, parent=parent)
        self.id = info["dir_id"]
        self.__children = []
        if children:
            direct_children = list(filter(
                lambda x: x["parent_dir_id"] == self.id, children))
            for c in direct_children:
                children.remove(c)
            for c in direct_children:
                child = TreeFolder(c, parent=self, children=children, data=data)
                self.__children.append(child)
        self._dirtable = DirTable(data, self.lba, block_size)
        file_entries = self._dirtable.get_entries()

        files = []
        for entry in file_entries:
            files.append(TreeFile(entry, parent=self))
        files = files[2:]
        self.__children.extend(files)

    def get_child(self, name: str):
        return next(i for i in self.children if i.name == name)

    @property
    def children(self):
        return self.__children


class Ps2Iso:
    def __init__(self, filename: str | os.PathLike, mutable: bool=False):
        self._set_logger()
        if mutable:
            self.log.info(f"Loading {filename}, this may take a while...")
            with open(filename, "rb") as f:
                self.data = f.read()
        else:
            self.data = FileBytes(filename)
        self.pvd = PVD(self.data)
        self.block_size = self.pvd.logical_block_size

        if self.pvd.system_identifier != "PLAYSTATION":
            self.log.warning((
                f"system_identifier is: '{self.pvd.system_identifier}', "
                "but should be 'PLAYSTATION'"))
            self.log.warning(
                f"{filename} may not be a PS2 ISO file")
        if self.block_size != 2048:
            self.log.warning((
                f"logical_block_size is: {self.block_size}, "
                "but should be 2048"))
            self.log.warning(
                f"{filename} may not be a PS2 ISO file")

        self.path_tables = PathTables(self.data, self.pvd)
        self.tree = self.path_tables.get_path_tree()

    def get_object(self, path: str):
        paths = path.split("/")
        if paths[0] == "":
            paths.pop(0)
        mark = self.tree
        for p in paths:
            mark = mark.get_child(p)
        return mark

    def get_blocks_allocated(self, path):
        obj = self.get_object(path)
        lba_list = self.get_lba_list()
        obj_idx = next(idx for idx, i in enumerate(lba_list) if i[1] == path)
        lba = lba_list[obj_idx][0]
        next_lba = lba_list[obj_idx + 1][0]
        return next_lba - lba

    def get_lba(self, path):
        return self.get_object(path).lba

    def replace_files(self, replacements, allow_move=False):
        paths = [path for path, _ in replacements]
        bins = [b for _, b in replacements]
        sizes = [len(b)//8 for b in bins]
        blocks_required = [ceil(len(b)/8/self.block_size) for b in bins]
        curr_lba = [self.get_lba(p) for p in paths]
        curr_blocks_allocated = [self.get_blocks_allocated(p) for p in paths]

        items = [
            {
                "path": p,
                "bin": b,
                "size": s,
                "blocks_required": br,
                "curr_lba": cl,
                "curr_blocks_allocated": cb
            } for p, b, s, br, cl, cb in
            zip(paths, bins, sizes, blocks_required, curr_lba,
                curr_blocks_allocated)]

        overflows = []
        for i in items:
            if i["blocks_required"] > i["curr_blocks_allocated"]:
                overflows.append(i)
        for o in overflows:
            self.log.warning((
                f"{o['path']} (size: {o['size']} "
                f"requires {o['blocks_required']} blocks, "
                f"{o['curr_blocks_allocated']} available"))

        if overflows and not allow_move:
            raise ValueError("allow_move must be true to increase file sizes")

        for i in items:
            lba = i["curr_lba"]
            num_blocks =  i["curr_blocks_allocated"]
            self.clear_blocks(lba, num_blocks)
        if not allow_move:
            for i in items:
                i["new_lba"] = i["curr_lba"]
                b = i["bin"]
                offset = i["curr_lba"]*self.block_size*8
                self.data.overwrite(b, offset)
        else:
            raise NotImplementedError("Moving files is not supported yet")

        for i in items:
            self.update_toc(i["path"], i["new_lba"], i["size"])

    def update_toc(self, path, lba, size):
        self.get_object(path).update_toc(lba, size)

    def write(self, filename):
        with open(filename, "wb") as f:
            self.data.tofile(f)

    def clear_blocks(self, start_block, num_blocks):
        start_addr = start_block*self.block_size*8
        end_addr = start_addr + num_blocks*self.block_size*8
        self.data.set(0, range(start_addr, end_addr))

    def get_lba_list(self):
        root = self.tree
        lba_list = self._get_lba_list(root)
        lba_list = list(set(lba_list))
        return sorted(lba_list, key=lambda x: x[0])

    def _get_lba_list(self, item, lba_list=None):
        if lba_list is None:
            lba_list = []
        lba = item.lba
        path = item.path
        lba_list.append((lba, path))
        if isinstance(item, TreeFolder):
            for c in item.children:
                self._get_lba_list(c,lba_list=lba_list)
        return lba_list

    def _get_blocks(self, lba, blocks=None, size=None):
        if blocks and size is None:
            size = blocks*self.block_size
        if size is None:
            raise ValueError("blocks/size must be set")

    def _set_logger(self):
        self.log = logging.getLogger("Ps2Iso")
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.log.addHandler(handler)
        self.log.setLevel(logging.INFO)


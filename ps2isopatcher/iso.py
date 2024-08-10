# https://wiki.osdev.org/ISO_9660
from pathlib import Path
from typing import Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
import logging
from math import ceil

from ps2isopatcher.util import FileBytes, both_endian_int


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

    def __init__(self, iso: "Ps2Iso"):
        """The Primary Volume Descriptor of an ISO9660 file

        Args:
            data: the contents of the ISO file
        """
        self.data = iso.data[
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

@dataclass
class ObjectEntry:
    name: str
    lba: int

@dataclass
class FileEntry(ObjectEntry):
    size: int

@dataclass
class PathTableEntry(ObjectEntry):
    parent_dir_id: int
    dir_id: int

class PathTable(ABC):
    def __init__(self, iso: "Ps2Iso", addr: int, size: int):
        """A path table describing where every file/folder is on disk

        Args:
            iso: main iso class
            addr: address of path table
            size: size of path table
        """
        self.tbl_data = iso.data[addr:(addr+size)]

    def get_entries(self) -> list[PathTableEntry]:
        """Get a list of all entries in the path table"""
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
            paths.append(PathTableEntry(
                name=name,
                lba=lba,
                parent_dir_id=parent_dir_id,
                dir_id=dir_id
            ))
            i += total_len
            dir_id += 1
        return paths

    def _get_name(self, entry: bytes, length: int) -> str:
        return entry[8:(8+length)].decode().strip()

    @abstractmethod
    def _get_lba(self, entry: bytes) -> int:
        pass

    @abstractmethod
    def _get_parent_dir_id(self, entry: bytes) -> int:
        pass


class LPathTable(PathTable):
    def _get_lba(self, entry: bytes) -> int:
        return int.from_bytes(entry[2:6], byteorder="little")

    def _get_parent_dir_id(self, entry) -> int:
        return int.from_bytes(entry[6:8], byteorder="little")

class MPathTable(PathTable):
    def _get_lba(self, entry: bytes) -> int:
        return int.from_bytes(entry[2:6], byteorder="big")

    def _get_parent_dir_id(self, entry) -> int:
        return int.from_bytes(entry[6:8], byteorder="big")

class PathTables:
    def __init__(self, iso: "Ps2Iso"):
        """Wrapper class to access the path tables on disk"""
        self._iso = iso
        size = iso.pvd.path_table_size
        lpt_addr = iso.pvd.l_path_table*2048
        mpt_addr = iso.pvd.m_path_table*2048
        self.l_path_table = LPathTable(iso, lpt_addr, size)
        self.m_path_table = MPathTable(iso, mpt_addr, size)

    def get_path_tree(self) -> "TreeFolder":
        paths = self.l_path_table.get_entries()
        root = paths.pop(0)
        return TreeFolder(self._iso, root, children=paths)


class DirTable:
    def __init__(self, iso: "Ps2Iso", lba: int):
        """Directory table showing all files inside of a folder

        Args:
            lba: block number where the table is

        """
        self._iso = iso
        self.dt_addr = lba*iso.block_size

    def get_entries(self) -> list[FileEntry]:
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
            entries.append(FileEntry(
                name=name,
                size=size,
                lba=lba,
            ))
            i += total_len
        return entries

    def set_entry(self, name: str, lba: int, size: int):
        idx = 0
        print(f"Searching for {name}")
        while True:
            total_len = self.tbl_data[idx]
            if total_len == 0:
                break
            entry = self.tbl_data[idx:(idx+total_len)]
            name_len = self._get_name_length(entry)
            n = self._get_name(entry, name_len)
            print(n)
            if n == name:
                iso_offset = idx + self.dt_addr
                lba_offset = iso_offset + 2
                size_offset = iso_offset + 10
                lba_bytes = both_endian_int(lba)
                size_bytes = both_endian_int(size)
                self._iso.overwrite(lba_bytes, lba_offset)
                self._iso.overwrite(size_bytes, size_offset)
                break
            idx += total_len

    @property
    def tbl_data(self) -> bytes:
        return self._iso.data[
            self.dt_addr:(self.dt_addr+self._iso.block_size)
        ]

    def _get_lba(self, entry) -> int:
        return int.from_bytes(entry[2:6], byteorder="little")

    def _get_size(self, entry) -> int:
        return int.from_bytes(entry[10:14], byteorder="little")

    def _get_name_length(self, entry) -> int:
        return int.from_bytes(entry[32:33], byteorder="little")

    def _get_name(self, entry, length) -> str:
        return entry[33:(33+length)].decode().strip()


class TreeObject:
    def __init__(
            self, iso: "Ps2Iso", entry: ObjectEntry,
            parent: Optional["TreeFolder"]=None
        ):
        self._iso = iso
        self._entry = entry
        self.__parent = parent

    @property
    def parent(self):
        return self.__parent

    @property
    def name(self):
        return self._entry.name

    @property
    def lba(self):
        return self._entry.lba

    @property
    def path(self):
        if self.parent is None:
            return ""
        return f"{self.parent.path}/{self.name}"

    def update_toc(self, lba: int, size: int):
        self.parent._dirtable.set_entry(self.name, lba, size)


class TreeFile(TreeObject):
    @property
    def size(self) -> int:
        return self._entry.size

    @property
    def data(self) -> bytes:
        start = self.lba*self._iso.block_size
        end = start + self.size
        return self._iso.data[start:end]

    def export(
            self,
            target_dir: str | os.PathLike,
            preserve_path: bool=True,
            include_version: bool=False,
        ):
        """Export a file to the local file system

        Args:
            target_dir: the folder to export to
            preserve_path: set to True to export with the full folder structure
                           set to False to only export the file
            include_version: set to True to include the version number in the filename
        """
        target_dir = Path(target_dir)
        if preserve_path:
            # Skip leading slash
            full_dir = target_dir / Path(self.path[1:]).parent
        else:
            full_dir = target_dir
        full_dir.mkdir(parents=True, exist_ok=True)
        if include_version:
            name = Path(self.path).name
        else:
            name = Path(self.path).name.rsplit(";", 1)[0]
        with open(full_dir / name, "wb") as f:
            f.write(self.data)


class TreeFolder(TreeObject):
    def __init__(
            self, iso: "Ps2Iso", entry: PathTableEntry, parent=None,
            children: Optional[list[PathTableEntry]]=None,
        ):
        super().__init__(iso, entry, parent=parent)
        self._children: list[TreeObject] = []
        if children:
            direct_children = list(filter(
                lambda x: x.parent_dir_id == self.id, children))
            for c in direct_children:
                children.remove(c)
            for c in direct_children:
                child = TreeFolder(
                    self._iso, c, parent=self, children=children)
                self._children.append(child)
        self._dirtable = DirTable(self._iso, self.lba)
        file_entries = self._dirtable.get_entries()

        files = []
        for entry in file_entries:
            files.append(TreeFile(self._iso, entry, parent=self))
        # Skip the "." and ".." entries
        files = files[2:]
        self._children.extend(files)

    def get_child(self, name: str) -> TreeObject:
        return next(i for i in self.children if i.name == name)

    @property
    def children(self) -> list[TreeObject]:
        return self._children

    @property
    def id(self) -> int:
        return self._entry.dir_id


class Ps2Iso:
    def __init__(self, filename: str | os.PathLike, mutable: bool=False):
        """A class to manipulate PS2 ISOs (ISO9660)

        Args:
            filename: path to an ISO file
            mutable: set to True to allow modifying of the data in memory (SLOW)
        """
        self._set_logger()
        if mutable:
            self.log.info(f"Loading {filename}, this may take a while...")
            with open(filename, "rb") as f:
                self.data = bytearray(f.read())
        else:
            self.data = FileBytes(filename)
        self.pvd = PVD(self)
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

        self.path_tables = PathTables(self)
        self._tree = self.path_tables.get_path_tree()

    @property
    def tree(self):
        return self._tree

    def get_object(self, path: str) -> TreeObject:
        paths = path.split("/")
        if paths[0] == "":
            paths.pop(0)
        mark = self.tree
        for p in paths:
            mark = mark.get_child(p)
        return mark

    def get_blocks_allocated(self, path: str) -> int:
        """Get the number of blocks currently available to a path"""
        lba_list = self.get_lba_list()
        obj_idx = next(idx for idx, i in enumerate(lba_list) if i[1] == path)
        lba = lba_list[obj_idx][0]
        try:
            next_lba = lba_list[obj_idx + 1][0]
        except IndexError:
            obj: TreeFile = self.get_object(path)
            return self.blocks_required(obj.data)
        return next_lba - lba

    def get_lba(self, path):
        return self.get_object(path).lba

    def get_next_free_block(self) -> int:
        lba, path = self.get_lba_list()[-1]
        num_blocks = self.get_blocks_allocated(path)
        return lba + num_blocks

    def replace_files(self, replacements: tuple[str, bytes], allow_move=False):
        paths = [path for path, _ in replacements]
        bins = [b for _, b in replacements]
        sizes = [len(b) for b in bins]
        blocks_required = [self.blocks_required(b) for b in bins]
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
                offset = i["curr_lba"]*self.block_size
                self.overwrite(i["bin"], offset)
                self.update_toc(i["path"], i["new_lba"], i["size"])
        else:
            # Ideally we would try to insert a few blocks to fit our data,
            # but that would involve shifting all the objects that exist beyond,
            # kind of a pain, may also cause issues in some cases if the game
            # hardcodes an address.
            # Instead, we take the lazy approach and just move the file to the
            # end of the image. This will result in a balooning file size, but
            # hopefully compressing to .chd will make it less of a problem
            for i in items:
                i["new_lba"] = self.get_next_free_block()
                offset = i["new_lba"]*self.block_size
                self.overwrite(i["bin"], offset)
                self.update_toc(i["path"], i["new_lba"], i["size"])

    def update_toc(self, path, lba, size):
        self.get_object(path).update_toc(lba, size)

    def write(self, filename):
        with open(filename, "wb") as f:
            f.write(self.data)

    def clear_blocks(self, start_block, num_blocks):
        start_addr = start_block*self.block_size
        blank_data = bytes(num_blocks*self.block_size)
        self.overwrite(blank_data, start_addr)

    def get_lba_list(self) -> list[tuple[int, str]]:
        """Get a list containing all paths on disk and their associated lba"""
        root = self.tree
        lba_list = self._get_lba_list(root)
        lba_list = list(set(lba_list))
        return sorted(lba_list, key=lambda x: x[0])

    def overwrite(self, data: bytes, addr: int):
        """Overwrite the underlying data on the disk

        Args:
            data: data to overwrite
            addr: address to start writing at
        """
        if not isinstance(self.data, bytearray):
            raise ValueError("Can not mutate an immutable Ps2Iso")
        end_addr = addr + len(data)
        diff = end_addr - len(self.data)
        if diff > 0:
            num_blocks = self.blocks_required(diff)
            self.data += bytearray(num_blocks*self.block_size)
        self.data[addr:addr + len(data)] = data

    def blocks_required(self, data: bytes | int) -> int:
        """Calculate the blocks required to store data"""
        if isinstance(data, (bytes, bytearray)):
            size = len(data)
        if isinstance(data, int):
            size = data
        return ceil(size/self.block_size)

    def _get_lba_list(self, item: TreeObject, lba_list=None):
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

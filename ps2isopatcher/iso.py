import logging
from bitstring import Bits


class PVD:
    PVD_OFFSET = 0x8000
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

    def __init__(self, data):
        self.data = data[
            self.PVD_OFFSET*8:(self.PVD_OFFSET+self.PVD_LENGTH)*8]

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
    
    def _get_intle(self, offset, length):
        e = self._get_entry(offset, length)
        return e.intle

    def _get_intme(self, offset, length):
        e = self._get_entry(offset, length)
        return e.intme
    
    def _get_str(self, offset, length):
        e = self._get_entry(offset, length)
        return e.tobytes().decode().strip()

    def _get_entry(self, offset, length):
        return self.data[offset*8:(offset+length)*8]

class PathTable:
    def __init__(self, data):
        self.data = data
        self.length = len(data)/8
    
    def get_paths(self):
        paths = []

        i = 0
        dir_id = 1
        while i < self.length:
            name_len = self.data[i*8:(i+1)*8].int
            total_len = name_len + 8
            if name_len % 2:
                total_len += 1
            entry = self.data[i*8:(i+total_len)*8]
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
    
    def _get_name(self, entry, length):
        return entry[8*8:(8+length)*8].tobytes().decode().strip()

    def _get_lba(self, entry):
        pass
    
    def _get_parent_dir_id(self, entry):
        pass


class LPathTable(PathTable):
    def _get_lba(self, entry):
        return entry[2*8:6*8].intle

    def _get_parent_dir_id(self, entry):
        return entry[6*8:8*8].intle

class PathTables:
    def __init__(self, data, pvd):
        size = pvd.path_table_size*8
        lpt_addr = pvd.l_path_table*2048*8
        self.l_path_table = LPathTable(data[lpt_addr:(lpt_addr+size)])


class Ps2Iso:
    def __init__(self, filename):
        self._set_logger()
        self.data = Bits(filename=filename)
        self.pvd = PVD(self.data)
        self.block_size = self.pvd.logical_block_size
        self.path_tables = PathTables(self.data, self.pvd)

        if self.pvd.system_identifier != "PLAYSTATION":
            self.log.warning((
                f"system_identifier: '{self.pvd.system_identifier}', "
                "should be 'PLAYSTATION'"))
            self.log.warning(
                f"{filename} may not be a PS2 ISO file")
        if self.block_size != 2048:        
            self.log.warning((
                f"logical_block_size: {self.block_size}, "
                "should be 2048"))
            self.log.warning(
                f"{filename} may not be a PS2 ISO file")
    

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

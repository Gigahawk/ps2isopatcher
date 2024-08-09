import os

class FileBytes(bytes):
    def __new__(cls, filename):
        instance = super().__new__(cls)
        instance.file = open(filename, 'rb')
        instance.__file_size = instance._get_file_size()
        return instance

    @property
    def file_size(self) -> int:
        return self.__file_size

    def __getitem__(self, index: int | slice) -> int | bytes:
        if isinstance(index, slice):
            start, stop, step = index.indices(self.file_size)
            self.file.seek(start, os.SEEK_SET)
            return self.file.read(stop - start)[::step]
        elif isinstance(index, int):
            if index < 0:
                index += self.__file_size
            self.file.seek(index, os.SEEK_SET)
            return self.file.read(1)[0]
        else:
            raise TypeError("Index must be an integer or slice")

    def __len__(self) -> int:
        return self.file_size

    def _get_file_size(self) -> int:
        current_position = self.file.tell()
        self.file.seek(0, os.SEEK_END)
        size = self.file.tell()
        self.file.seek(current_position, os.SEEK_SET)
        return size

    def close(self):
        self.file.close()

    def __del__(self):
        self.close()


def both_endian_int(val: int) -> bytes:
    le = val.to_bytes(length=4, byteorder="little")
    be = val.to_bytes(length=4, byteorder="big")
    return le + be
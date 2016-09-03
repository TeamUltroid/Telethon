from io import BytesIO, BufferedReader
from tl.all_tlobjects import tlobjects
from struct import unpack
import os


class BinaryReader:
    """
    Small utility class to read binary data.
    Also creates a "Memory Stream" if necessary
    """
    def __init__(self, data=None, stream=None):
        if data:
            self.stream = BytesIO(data)
        elif stream:
            self.stream = stream
        else:
            raise ValueError("Either bytes or a stream must be provided")

        self.reader = BufferedReader(self.stream)

    # region Reading

    # "All numbers are written as little endian." |> Source: https://core.telegram.org/mtproto
    def read_byte(self):
        """Reads a single byte value"""
        return self.read(1)[0]

    def read_int(self, signed=True):
        """Reads an integer (4 bytes) value"""
        return int.from_bytes(self.read(4), byteorder='little', signed=signed)

    def read_long(self, signed=True):
        """Reads a long integer (8 bytes) value"""
        return int.from_bytes(self.read(8), byteorder='little', signed=signed)

    def read_float(self):
        """Reads a real floating point (4 bytes) value"""
        return unpack('<f', self.read(4))[0]

    def read_double(self):
        """Reads a real floating point (8 bytes) value"""
        return unpack('<d', self.read(8))[0]

    def read_large_int(self, bits, signed=True):
        """Reads a n-bits long integer value"""
        return int.from_bytes(self.read(bits // 8), byteorder='little', signed=signed)

    def read(self, length):
        """Read the given amount of bytes"""
        result = self.reader.read(length)
        if len(result) != length:
            raise BufferError('Trying to read outside the data bounds (no more data left to read)')
        
        return result

    def get_bytes(self):
        """Gets the byte array representing the current buffer as a whole"""
        return self.stream.getvalue()

    # endregion

    # region Telegram custom reading

    def tgread_bytes(self):
        """Reads a Telegram-encoded byte array, without the need of specifying its length"""
        first_byte = self.read_byte()
        if first_byte == 254:
            length = self.read_byte() | (self.read_byte() << 8) | (self.read_byte() << 16)
            padding = length % 4
        else:
            length = first_byte
            padding = (length + 1) % 4

        data = self.read(length)
        if padding > 0:
            padding = 4 - padding
            self.read(padding)

        return data

    def tgread_string(self):
        """Reads a Telegram-encoded string"""
        return str(self.tgread_bytes(), encoding='utf-8')

    def tgread_object(self):
        """Reads a Telegram object"""
        id = self.read_int()
        clazz = tlobjects.get(id, None)
        if clazz is None:
            raise ImportError('Could not find a matching ID for the TLObject that was supposed to be read. '
                              'Found ID: {}'.format(hex(id)))

        # Instantiate the class and return the result
        result = clazz()
        result.on_response(self)
        return result

    # endregion

    def close(self):
        self.reader.close()
        # TODO Do I need to close the underlying stream?

    # region Position related

    def tell_position(self):
        """Tells the current position on the stream"""
        return self.reader.tell()

    def set_position(self, position):
        """Sets the current position on the stream"""
        self.reader.seek(position)

    def seek(self, offset):
        """Seeks the stream position given an offset from the current position. May be negative"""
        self.reader.seek(offset, os.SEEK_CUR)

    # endregion

    # region with block

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # endregion

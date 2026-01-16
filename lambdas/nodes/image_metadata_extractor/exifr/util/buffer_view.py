"""
BufferView - A class for reading binary data with specified endianness
Ported from BufferView.mjs
"""

import struct


class BufferView:
    """
    A view into a buffer that allows reading various data types
    with big-endian or little-endian byte order
    """

    def __init__(self, data, offset=0, length=None, big_endian=True):
        """
        Initialize BufferView

        Args:
            data: bytes, bytearray, memoryview, or BufferView
            offset: starting offset in the data
            length: length of the view (None = rest of data)
            big_endian: True for big-endian, False for little-endian
        """
        # Handle BufferView input using duck typing - check for _data attribute
        if (
            hasattr(data, "_data")
            and hasattr(data, "_offset")
            and hasattr(data, "_big_endian")
        ):
            # This is a BufferView instance - just use its underlying data
            self._data = data._data
            # Adjust offset to account for the BufferView's own offset
            self._offset = data._offset + offset
            self._big_endian = (
                big_endian if big_endian is not None else data._big_endian
            )
        elif isinstance(data, (bytes, bytearray)):
            self._data = memoryview(data)
            self._offset = offset
            self._big_endian = big_endian
        elif isinstance(data, memoryview):
            self._data = data
            self._offset = offset
            self._big_endian = big_endian
        else:
            raise TypeError("Data must be bytes, bytearray, memoryview, or BufferView")

        if length is None:
            self._length = len(self._data) - offset
        else:
            self._length = length

        # Byte order prefix for struct
        self._endian = ">" if big_endian else "<"

        # BufferView has all data loaded, not chunked
        self.chunked = False

    async def ensure_chunk(self, offset, length):
        """
        Ensure chunk is available (no-op for BufferView since all data is in memory)

        Args:
            offset: Offset to ensure
            length: Length to ensure
        """
        # No-op for non-chunked readers - all data is already in memory

    @property
    def byte_length(self):
        """Total length of the view"""
        return self._length

    @property
    def byte_offset(self):
        """Starting offset in the underlying buffer"""
        return self._offset

    @property
    def big_endian(self):
        """Whether this view uses big-endian byte order"""
        return self._big_endian

    def _check_bounds(self, offset, size):
        """Check if read is within bounds"""
        if offset < 0 or offset + size > self._length:
            raise IndexError(
                f"Read at offset {offset} with size {size} is out of bounds (length: {self._length})"
            )

    def get_uint8(self, offset):
        """Read unsigned 8-bit integer"""
        self._check_bounds(offset, 1)
        return self._data[self._offset + offset]

    def get_int8(self, offset):
        """Read signed 8-bit integer"""
        self._check_bounds(offset, 1)
        val = self._data[self._offset + offset]
        return val if val < 128 else val - 256

    def get_uint16(self, offset):
        """Read unsigned 16-bit integer"""
        self._check_bounds(offset, 2)
        start = self._offset + offset
        data = bytes(self._data[start : start + 2])
        return struct.unpack(f"{self._endian}H", data)[0]

    def get_int16(self, offset):
        """Read signed 16-bit integer"""
        self._check_bounds(offset, 2)
        start = self._offset + offset
        data = bytes(self._data[start : start + 2])
        return struct.unpack(f"{self._endian}h", data)[0]

    def get_uint32(self, offset):
        """Read unsigned 32-bit integer"""
        self._check_bounds(offset, 4)
        start = self._offset + offset
        data = bytes(self._data[start : start + 4])
        return struct.unpack(f"{self._endian}I", data)[0]

    def get_int32(self, offset):
        """Read signed 32-bit integer"""
        self._check_bounds(offset, 4)
        start = self._offset + offset
        data = bytes(self._data[start : start + 4])
        return struct.unpack(f"{self._endian}i", data)[0]

    def get_float32(self, offset):
        """Read 32-bit float"""
        self._check_bounds(offset, 4)
        start = self._offset + offset
        data = bytes(self._data[start : start + 4])
        return struct.unpack(f"{self._endian}f", data)[0]

    def get_float64(self, offset):
        """Read 64-bit float (double)"""
        self._check_bounds(offset, 8)
        start = self._offset + offset
        data = bytes(self._data[start : start + 8])
        return struct.unpack(f"{self._endian}d", data)[0]

    def get_uint64(self, offset):
        """Read unsigned 64-bit integer"""
        self._check_bounds(offset, 8)
        start = self._offset + offset
        data = bytes(self._data[start : start + 8])
        return struct.unpack(f"{self._endian}Q", data)[0]

    def get_bytes(self, offset, length):
        """Read bytes from the view"""
        self._check_bounds(offset, length)
        start = self._offset + offset
        return bytes(self._data[start : start + length])

    def get_string(self, offset, length, encoding="utf-8"):
        """Read string from the view"""
        data = self.get_bytes(offset, length)
        # Remove null terminator if present
        null_pos = data.find(b"\x00")
        if null_pos >= 0:
            data = data[:null_pos]
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            return data.decode(encoding, errors="ignore")

    def get_latin1_string(self, offset, length):
        """Read Latin-1 encoded string from the view"""
        return self.get_string(offset, length, encoding="latin-1")

    def get_unicode_string(self, offset, length):
        """Read Unicode (UTF-16) encoded string from the view"""
        return self.get_string(offset, length, encoding="utf-16")

    def get_uint8_array(self, offset, length=None):
        """Read array of unsigned 8-bit integers"""
        if length is None:
            length = self.byte_length - offset
        return list(self.get_bytes(offset, length))

    def subarray(self, offset, length=None):
        """
        Create a new view of a subarray

        Args:
            offset: Starting offset relative to this view
            length: Length of subarray (None = rest of data)

        Returns:
            BufferView: New view of the subarray
        """
        if length is None:
            length = self._length - offset
        return BufferView(self._data, self._offset + offset, length, self._big_endian)

    def set_endian(self, big_endian):
        """Change the endianness of this view"""
        self._big_endian = big_endian
        self._endian = ">" if big_endian else "<"

    def __len__(self):
        """Return the length of the view"""

    def get_uint_bytes(self, offset, size):
        """
        Read unsigned integer of variable size

        Args:
            offset: Offset to read from
            size: Number of bytes (1, 2, 4, or 8)

        Returns:
            int: Unsigned integer value
        """
        if size == 1:
            return self.get_uint8(offset)
        elif size == 2:
            return self.get_uint16(offset)
        elif size == 4:
            return self.get_uint32(offset)
        elif size == 8:
            return self.get_uint64(offset)
        else:
            raise ValueError(f"Unsupported size: {size}. Must be 1, 2, 4, or 8")

        return self._length

    def __getitem__(self, key):
        """Allow array-like access"""
        if isinstance(key, slice):
            start = key.start or 0
            stop = key.stop or self._length
            return self.get_bytes(start, stop - start)
        else:
            return self.get_uint8(key)

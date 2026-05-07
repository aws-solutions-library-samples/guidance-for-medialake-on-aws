"""
File reader implementations
Ported from file-readers/*.mjs
"""

from pathlib import Path

from .plugins import file_readers
from .util.buffer_view import BufferView


class FsReader:
    """File system reader for local files"""

    def __init__(self, file_path, options):
        self.file_path = Path(file_path)
        self.options = options
        self.chunk_size = getattr(options, "chunkSize", None) if options else None
        self._buffer = None
        # For now, not implementing chunked reading
        self.chunked = False

    async def read(self):
        """Read the file"""
        # For now, just read the entire file
        # TODO: Implement chunked reading if chunk_size is set
        with open(self.file_path, "rb") as f:
            data = f.read()
        self._buffer = BufferView(data)
        return self._buffer

    def get_buffer_view(self):
        """Get the buffer view"""
        return self._buffer

    def __getattr__(self, name):
        """Delegate unknown attributes to buffer view"""
        if "_buffer" in self.__dict__ and self._buffer is not None:
            return getattr(self._buffer, name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )


class BlobReader:
    """Reader for bytes/blob data"""

    def __init__(self, data, options):
        self.data = data
        self.options = options
        self._buffer = None
        self.chunked = False

    async def read(self):
        """Read the blob"""
        if isinstance(self.data, (bytes, bytearray)):
            self._buffer = BufferView(self.data)
        elif isinstance(self.data, memoryview):
            self._buffer = BufferView(self.data)
        else:
            # Try to read if it's file-like
            if hasattr(self.data, "read"):
                data = self.data.read()
                if isinstance(data, str):
                    data = data.encode("latin-1")
                self._buffer = BufferView(data)
            else:
                raise TypeError(f"Cannot create BlobReader from {type(self.data)}")
        return self._buffer

    def get_buffer_view(self):
        """Get the buffer view"""
        return self._buffer

    def __getattr__(self, name):
        """Delegate unknown attributes to buffer view"""
        if self._buffer:
            return getattr(self._buffer, name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )


class Base64Reader:
    """Reader for base64 encoded data"""

    def __init__(self, data_url, options):
        self.data_url = data_url
        self.options = options
        self._buffer = None
        self.chunked = False

    async def read(self):
        """Read and decode base64 data"""
        import base64

        if self.data_url.startswith("data:"):
            # Extract base64 data after comma
            _, encoded = self.data_url.split(",", 1)
            decoded = base64.b64decode(encoded)
        else:
            # Assume entire string is base64
            decoded = base64.b64decode(self.data_url)

        self._buffer = BufferView(decoded)
        return self._buffer

    def get_buffer_view(self):
        """Get the buffer view"""
        return self._buffer

    def __getattr__(self, name):
        """Delegate unknown attributes to buffer view"""
        if self._buffer:
            return getattr(self._buffer, name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )


class UrlFetcher:
    """Reader for fetching data from URLs"""

    def __init__(self, url, options):
        self.url = url
        self.options = options
        self._buffer = None
        self.chunked = False

    async def read(self):
        """Fetch and read URL data"""
        try:
            # Try aiohttp first for async support
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as response:
                    response.raise_for_status()
                    data = await response.read()
        except ImportError:
            # Fall back to requests (blocking)
            try:
                import requests

                response = requests.get(self.url)
                response.raise_for_status()
                data = response.content
            except ImportError:
                # Final fallback to urllib
                import urllib.request

                with urllib.request.urlopen(self.url) as response:
                    data = response.read()

        self._buffer = BufferView(data)
        return self._buffer

    def get_buffer_view(self):
        """Get the buffer view"""
        return self._buffer

    def __getattr__(self, name):
        """Delegate unknown attributes to buffer view"""
        if self._buffer:
            return getattr(self._buffer, name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )


# Register readers
file_readers["fs"] = FsReader
file_readers["blob"] = BlobReader
file_readers["base64"] = Base64Reader
file_readers["url"] = UrlFetcher

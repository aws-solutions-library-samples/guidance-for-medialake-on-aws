"""
File reader system
Ported from reader.mjs
"""

import base64
from pathlib import Path

from .plugins import file_readers
from .util.buffer_view import BufferView
from .util.helpers import throw_error

INVALID_INPUT = "Invalid input argument"


async def read(arg, options):
    """
    Read input and return a file view

    Args:
        arg: File path, URL, bytes, or file-like object
        options: Options instance

    Returns:
        BufferView or file reader instance
    """
    if isinstance(arg, str):
        return await read_string(arg, options)
    elif isinstance(arg, (bytes, bytearray)):
        return BufferView(arg)
    elif isinstance(arg, memoryview):
        return BufferView(arg)
    elif hasattr(arg, "read"):
        # File-like object
        return await read_file_like(arg, options)
    elif isinstance(arg, Path):
        return await read_string(str(arg), options)
    else:
        throw_error(INVALID_INPUT)


async def read_string(arg, options):
    """
    Read from string (path, URL, or base64)

    Args:
        arg: String input
        options: Options instance

    Returns:
        File reader or BufferView
    """
    if is_base64_url(arg):
        return await call_reader_class(arg, options, "base64")
    elif "://" in arg:
        # URL
        return await call_reader(arg, options, "url", fetch_url_as_bytes)
    else:
        # File path
        return await call_reader_class(arg, options, "fs")


async def read_file_like(file_obj, options):
    """
    Read from file-like object

    Args:
        file_obj: File-like object with read() method
        options: Options instance

    Returns:
        BufferView or file reader
    """
    # Try to get the file path if available
    if hasattr(file_obj, "name"):
        return await call_reader_class(file_obj.name, options, "fs")
    else:
        # Read entire file into memory
        data = file_obj.read()
        if isinstance(data, str):
            data = data.encode("latin-1")
        return BufferView(data)


async def call_reader(url, options, reader_name, reader_fn):
    """
    Call a file reader by name or function

    Args:
        url: Input URL or path
        options: Options instance
        reader_name: Name of the reader
        reader_fn: Fallback function if reader not loaded

    Returns:
        File reader or BufferView
    """
    if file_readers.has(reader_name):
        return await call_reader_class(url, options, reader_name)
    elif reader_fn:
        return await call_reader_function(url, reader_fn)
    else:
        throw_error(f"Parser {reader_name} is not loaded")


async def call_reader_class(input_arg, options, reader_name):
    """
    Instantiate and call a reader class

    Args:
        input_arg: Input argument
        options: Options instance
        reader_name: Name of the reader

    Returns:
        File reader instance
    """
    Reader = file_readers.get(reader_name)
    file_reader = Reader(input_arg, options)
    await file_reader.read()
    return file_reader


async def call_reader_function(input_arg, reader_fn):
    """
    Call a reader function and wrap result in BufferView

    Args:
        input_arg: Input argument
        reader_fn: Reader function

    Returns:
        BufferView instance
    """
    raw_data = await reader_fn(input_arg)
    return BufferView(raw_data)


# Fallback full-file readers


async def fetch_url_as_bytes(url):
    """
    Fetch URL and return bytes

    Args:
        url: URL to fetch

    Returns:
        bytes
    """
    try:
        import requests

        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except ImportError:
        # Try with urllib as fallback
        import urllib.request

        with urllib.request.urlopen(url) as response:
            return response.read()


def is_base64_url(string):
    """
    Check if string is a base64 data URL

    Args:
        string: String to check

    Returns:
        bool
    """
    return string.startswith("data:") or len(string) > 10000


async def read_base64_string(data_url):
    """
    Read base64 data URL

    Args:
        data_url: Base64 data URL string

    Returns:
        bytes
    """
    if data_url.startswith("data:"):
        # Extract base64 data after comma
        _, encoded = data_url.split(",", 1)
        return base64.b64decode(encoded)
    else:
        # Assume entire string is base64
        return base64.b64decode(data_url)

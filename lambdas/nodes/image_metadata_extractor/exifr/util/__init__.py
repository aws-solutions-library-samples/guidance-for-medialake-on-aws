"""
Utility modules for exifr
"""

from .buffer_view import BufferView
from .helpers import object_assign, throw_error, undefined_if_empty
from .platform import browser, node, py_version

__all__ = [
    "BufferView",
    "throw_error",
    "undefined_if_empty",
    "object_assign",
    "browser",
    "node",
    "py_version",
]

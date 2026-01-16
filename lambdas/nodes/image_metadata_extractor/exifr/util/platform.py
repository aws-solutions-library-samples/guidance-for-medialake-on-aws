"""
Platform detection utilities
"""

import sys

# Python always runs in an environment similar to Node.js (not browser)
browser = False
node = True

# Python version info
py_version = sys.version_info
py_major = py_version[0]
py_minor = py_version[1]

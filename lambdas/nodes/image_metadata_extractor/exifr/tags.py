"""
Tag dictionaries and constants
Ported from tags.mjs
"""


class Dictionary(dict):
    """
    Extended dictionary for tag management
    Maintains lists of all keys and values for quick access
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._all_keys = None
        self._all_values = None

    @property
    def tag_keys(self):
        """Get list of all keys"""
        if self._all_keys is None:
            self._all_keys = list(self.keys())
        return self._all_keys

    @property
    def tag_values(self):
        """Get list of all values"""
        if self._all_values is None:
            self._all_values = list(self.values())
        return self._all_values

    def __setitem__(self, key, value):
        """Override setitem to invalidate cache"""
        super().__setitem__(key, value)
        self._all_keys = None
        self._all_values = None


def create_dictionary(group, key, entries):
    """
    Create a new dictionary and add it to a group

    Args:
        group: Dictionary group to add to
        key: Key or list of keys
        entries: List of (key, value) tuples
    """
    dictionary = Dictionary()
    for k, v in entries:
        dictionary[k] = v

    if isinstance(key, list):
        for k in key:
            group[k] = dictionary
    else:
        group[key] = dictionary

    return dictionary


def extend_dictionary(group, block_name, new_tags):
    """
    Extend an existing dictionary with new tags

    Args:
        group: Dictionary group
        block_name: Name of the block
        new_tags: List of (key, value) tuples
    """
    dictionary = group.get(block_name)
    if dictionary:
        for key, value in new_tags:
            dictionary[key] = value


# Global tag dictionaries
tag_keys = {}
tag_values = {}
tag_revivers = {}

# Tag constants
TAG_MAKERNOTE = 0x927C
TAG_USERCOMMENT = 0x9286
TAG_XMP = 0x02BC
TAG_IPTC = 0x83BB
TAG_PHOTOSHOP = 0x8649
TAG_ICC = 0x8773

TAG_IFD_EXIF = 0x8769
TAG_IFD_GPS = 0x8825
TAG_IFD_INTEROP = 0xA005

TAG_GPS_LATREF = 0x0001
TAG_GPS_LAT = 0x0002
TAG_GPS_LONREF = 0x0003
TAG_GPS_LON = 0x0004

TAG_ORIENTATION = 0x0112

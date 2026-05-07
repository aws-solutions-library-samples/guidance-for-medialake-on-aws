"""
Options handling system
Ported from options.mjs
"""

from .plugins import segment_parsers, throw_not_loaded
from .tags import (
    TAG_ICC,
    TAG_IFD_EXIF,
    TAG_IFD_GPS,
    TAG_IFD_INTEROP,
    TAG_IPTC,
    TAG_MAKERNOTE,
    TAG_USERCOMMENT,
    TAG_XMP,
    tag_keys,
)
from .util import platform, throw_error

# Configuration property groups
CHUNKED_PROPS = [
    "chunked",
    "firstChunkSize",
    "firstChunkSizeNode",
    "firstChunkSizeBrowser",
    "chunkSize",
    "chunkLimit",
]

# List of segments besides TIFF/EXIF
OTHER_SEGMENTS = ["jfif", "xmp", "icc", "iptc", "ihdr"]

# List of all segments
SEGMENTS = ["tiff"] + OTHER_SEGMENTS

# TIFF IFD blocks (order is important for correctly assigning pick tags)
TIFF_BLOCKS = ["ifd0", "ifd1", "exif", "gps", "interop"]

# All segments and blocks
SEGMENTS_AND_BLOCKS = SEGMENTS + TIFF_BLOCKS

# Notable extractable TIFF tags
TIFF_EXTRACTABLES = ["makerNote", "userComment"]

# Inheritable options
INHERITABLES = ["translateKeys", "translateValues", "reviveValues", "multiSegment"]

# All formatters
ALL_FORMATTERS = INHERITABLES + ["sanitize", "mergeOutput", "silentErrors"]


class SharedOptions:
    """Base class for shared option properties"""

    @property
    def translate(self):
        """Check if any translation is enabled"""
        return (
            getattr(self, "translateKeys", False)
            or getattr(self, "translateValues", False)
            or getattr(self, "reviveValues", False)
        )


class SubOptions(SharedOptions):
    """Options for a specific segment or block"""

    def __init__(self, key, default_value, user_value, parent):
        self.key = key
        self.enabled = default_value
        self.parse = self.enabled
        self.skip = set()
        self.pick = set()
        self.deps = set()  # Tags required by other blocks

        self.translateKeys = False
        self.translateValues = False
        self.reviveValues = False

        # Apply inheritable properties from parent
        self._apply_inheritables(parent)

        # Determine if this can be filtered (TIFF blocks only)
        self.can_be_filtered = key in TIFF_BLOCKS
        if self.can_be_filtered:
            dict_entry = tag_keys.get(key)
            self.dict = dict_entry if dict_entry else None
        else:
            self.dict = None

        # Process user value
        if user_value is not None:
            if isinstance(user_value, list):
                self.parse = self.enabled = True
                if self.can_be_filtered and len(user_value) > 0:
                    self._translate_tag_set(user_value, self.pick)
            elif isinstance(user_value, dict):
                self.enabled = True
                self.parse = user_value.get("parse", True)
                if self.can_be_filtered:
                    pick = user_value.get("pick", [])
                    skip = user_value.get("skip", [])
                    if pick and len(pick) > 0:
                        self._translate_tag_set(pick, self.pick)
                    if skip and len(skip) > 0:
                        self._translate_tag_set(skip, self.skip)
                self._apply_inheritables(user_value)
            elif isinstance(user_value, bool):
                self.parse = self.enabled = user_value
            else:
                throw_error(f"Invalid options argument: {user_value}")

    def _apply_inheritables(self, origin):
        """Apply inheritable properties from origin"""
        if isinstance(origin, dict):
            for key in INHERITABLES:
                if key in origin:
                    setattr(self, key, origin[key])
        else:
            for key in INHERITABLES:
                val = getattr(origin, key, None)
                if val is not None:
                    setattr(self, key, val)

    def _translate_tag_set(self, input_array, output_set):
        """Translate tag names to numeric codes"""
        if self.dict:
            tag_keys_list = self.dict.tag_keys
            tag_values_list = self.dict.tag_values

            for tag in input_array:
                if isinstance(tag, str):
                    # Try to find in values first
                    try:
                        index = tag_values_list.index(tag)
                        output_set.add(tag_keys_list[index])
                    except ValueError:
                        # Try as numeric string in keys
                        try:
                            tag_num = int(tag)
                            if tag_num in tag_keys_list:
                                output_set.add(tag_num)
                        except ValueError:
                            pass
                else:
                    output_set.add(tag)
        else:
            for tag in input_array:
                output_set.add(tag)

    def finalize_filters(self):
        """Finalize pick/skip filters"""
        if not self.enabled and len(self.deps) > 0:
            self.enabled = True
            self.pick.update(self.deps)
        elif self.enabled and len(self.pick) > 0:
            self.pick.update(self.deps)

    @property
    def needed(self):
        """Check if this segment/block is needed"""
        return self.enabled or len(self.deps) > 0


# Default options
DEFAULTS = {
    # Segments
    "jfif": False,
    "tiff": True,
    "xmp": False,
    "icc": False,
    "iptc": False,
    # TIFF blocks
    "ifd0": True,
    "ifd1": False,
    "exif": True,
    "gps": True,
    "interop": False,
    # PNG header (undefined so JPEG/HEIC don't pick it up)
    "ihdr": None,
    # Notable TIFF tags
    "makerNote": False,
    "userComment": False,
    # Multi-segment support
    "multiSegment": False,
    # Filters
    "skip": [],
    "pick": [],
    # Output formatters
    "translateKeys": True,
    "translateValues": True,
    "reviveValues": True,
    "sanitize": True,
    "mergeOutput": True,
    "silentErrors": True,
    # Chunked reader
    "chunked": True,
    "firstChunkSize": None,
    "firstChunkSizeNode": 512,
    "firstChunkSizeBrowser": 65536,
    "chunkSize": 65536,
    "chunkLimit": 5,
}


# Cache for options instances
_existing_instances = {}


class Options(SharedOptions):
    """Main options class"""

    default = DEFAULTS

    def __getitem__(self, key):
        """Allow subscript access: options['tiff']"""
        return getattr(self, key)

    def __contains__(self, key):
        """Allow 'in' operator"""
        return hasattr(self, key)

    @classmethod
    def use_cached(cls, user_options):
        """Get cached options instance or create new one"""
        # Use id() for dict/list, value for primitives
        if isinstance(user_options, (dict, list)):
            cache_key = id(user_options)
        else:
            cache_key = user_options

        if cache_key in _existing_instances:
            return _existing_instances[cache_key]

        options = cls(user_options)
        _existing_instances[cache_key] = options
        return options

    def __init__(self, user_options=None):
        if user_options is True:
            self._setup_from_true()
        elif user_options is None:
            self._setup_from_undefined()
        elif isinstance(user_options, list):
            self._setup_from_array(user_options)
        elif isinstance(user_options, dict):
            self._setup_from_object(user_options)
        else:
            throw_error(f"Invalid options argument: {user_options}")

        # Set first chunk size based on platform
        if self.firstChunkSize is None:
            self.firstChunkSize = (
                self.firstChunkSizeBrowser
                if platform.browser
                else self.firstChunkSizeNode
            )

        # Disable thumbnail if merging output
        if self.mergeOutput:
            self.ifd1.enabled = False

        # Process filters and dependencies
        self._filter_nested_segment_tags()
        self._traverse_tiff_dependency_tree()
        self._check_loaded_plugins()

    def _setup_from_undefined(self):
        """Setup with default values"""
        for key in CHUNKED_PROPS:
            setattr(self, key, DEFAULTS[key])
        for key in ALL_FORMATTERS:
            setattr(self, key, DEFAULTS[key])
        for key in TIFF_EXTRACTABLES:
            setattr(self, key, DEFAULTS[key])
        for key in SEGMENTS_AND_BLOCKS:
            setattr(self, key, SubOptions(key, DEFAULTS.get(key), None, self))

    def _setup_from_true(self):
        """Setup with everything enabled"""
        for key in CHUNKED_PROPS:
            setattr(self, key, DEFAULTS[key])
        for key in ALL_FORMATTERS:
            setattr(self, key, DEFAULTS[key])
        for key in TIFF_EXTRACTABLES:
            setattr(self, key, True)
        for key in SEGMENTS_AND_BLOCKS:
            setattr(self, key, SubOptions(key, True, None, self))

    def _setup_from_array(self, user_options):
        """Setup with array of tags to pick"""
        for key in CHUNKED_PROPS:
            setattr(self, key, DEFAULTS[key])
        for key in ALL_FORMATTERS:
            setattr(self, key, DEFAULTS[key])
        for key in TIFF_EXTRACTABLES:
            setattr(self, key, DEFAULTS[key])
        for key in SEGMENTS_AND_BLOCKS:
            setattr(self, key, SubOptions(key, False, None, self))
        self._setup_global_filters(user_options, None, TIFF_BLOCKS)

    def _setup_from_object(self, user_options):
        """Setup from options dictionary"""
        # Copy all user options
        for key, value in user_options.items():
            if key not in SEGMENTS_AND_BLOCKS:
                setattr(self, key, value)

        # Setup standard options
        for key in CHUNKED_PROPS:
            setattr(self, key, user_options.get(key, DEFAULTS[key]))
        for key in ALL_FORMATTERS:
            setattr(self, key, user_options.get(key, DEFAULTS[key]))
        for key in TIFF_EXTRACTABLES:
            setattr(self, key, user_options.get(key, DEFAULTS[key]))

        # Setup segments and blocks
        for key in SEGMENTS:
            setattr(
                self,
                key,
                SubOptions(key, DEFAULTS.get(key), user_options.get(key), self),
            )
        for key in TIFF_BLOCKS:
            setattr(
                self,
                key,
                SubOptions(key, DEFAULTS.get(key), user_options.get(key), self.tiff),
            )

        # Setup global filters
        self._setup_global_filters(
            user_options.get("pick"),
            user_options.get("skip"),
            TIFF_BLOCKS,
            SEGMENTS_AND_BLOCKS,
        )

        # Handle tiff shortcuts
        tiff_option = user_options.get("tiff")
        if tiff_option is True:
            self._batch_enable_with_bool(TIFF_BLOCKS, True)
        elif tiff_option is False:
            self._batch_enable_with_user_value(TIFF_BLOCKS, user_options)
        elif isinstance(tiff_option, list):
            self._setup_global_filters(tiff_option, None, TIFF_BLOCKS)
        elif isinstance(tiff_option, dict):
            self._setup_global_filters(
                tiff_option.get("pick"), tiff_option.get("skip"), TIFF_BLOCKS
            )

    def _batch_enable_with_bool(self, keys, value):
        """Enable/disable multiple keys with boolean"""
        for key in keys:
            getattr(self, key).enabled = value

    def _batch_enable_with_user_value(self, keys, user_options):
        """Enable keys based on user options"""
        for key in keys:
            user_option = user_options.get(key)
            getattr(self, key).enabled = user_option not in (False, None)

    def _setup_global_filters(
        self, pick, skip, dict_keys, disableable_segs_and_blocks=None
    ):
        """Setup global pick/skip filters"""
        if disableable_segs_and_blocks is None:
            disableable_segs_and_blocks = dict_keys

        if pick and len(pick) > 0:
            # Disable all blocks first when using pick
            for block_key in disableable_segs_and_blocks:
                getattr(self, block_key).enabled = False

            # Find which blocks contain the picked tags
            entries = _find_scopes_for_global_tag_array(pick, dict_keys)
            for block_key, tags in entries:
                block = getattr(self, block_key)
                block.pick.update(tags)
                block.enabled = True

        elif skip and len(skip) > 0:
            entries = _find_scopes_for_global_tag_array(skip, dict_keys)
            for block_key, tags in entries:
                getattr(self, block_key).skip.update(tags)

    def _filter_nested_segment_tags(self):
        """Filter nested segment tags (XMP, IPTC, ICC in TIFF)"""
        ifd0 = self.ifd0
        exif = self.exif
        xmp = self.xmp
        iptc = self.iptc
        icc = self.icc

        # Handle MakerNote and UserComment
        if self.makerNote:
            exif.deps.add(TAG_MAKERNOTE)
        else:
            exif.skip.add(TAG_MAKERNOTE)

        if self.userComment:
            exif.deps.add(TAG_USERCOMMENT)
        else:
            exif.skip.add(TAG_USERCOMMENT)

        # Handle segments that can be stored as tags
        if not xmp.enabled:
            ifd0.skip.add(TAG_XMP)
        if not iptc.enabled:
            ifd0.skip.add(TAG_IPTC)
        if not icc.enabled:
            ifd0.skip.add(TAG_ICC)

    def _traverse_tiff_dependency_tree(self):
        """Traverse TIFF block dependencies"""
        ifd0 = self.ifd0
        exif = self.exif
        gps = self.gps
        interop = self.interop

        # Setup dependencies
        if interop.needed:
            exif.deps.add(TAG_IFD_INTEROP)
            ifd0.deps.add(TAG_IFD_INTEROP)

        if exif.needed:
            ifd0.deps.add(TAG_IFD_EXIF)

        if gps.needed:
            ifd0.deps.add(TAG_IFD_GPS)

        # Enable TIFF if any block is enabled
        self.tiff.enabled = (
            any(getattr(self, key).enabled for key in TIFF_BLOCKS)
            or self.makerNote
            or self.userComment
        )

        # Finalize filters for all blocks
        for key in TIFF_BLOCKS:
            getattr(self, key).finalize_filters()

    @property
    def only_tiff(self):
        """Check if only TIFF segment is enabled"""
        if any(getattr(self, key).enabled for key in OTHER_SEGMENTS):
            return False
        return self.tiff.enabled

    def _check_loaded_plugins(self):
        """Check that required plugins are loaded"""
        for key in SEGMENTS:
            if getattr(self, key).enabled and not segment_parsers.has(key):
                throw_not_loaded("segment parser", key)


def _find_scopes_for_global_tag_array(tag_array, dict_keys):
    """Find which blocks contain the specified tags"""
    scopes = []

    for block_key in dict_keys:
        dictionary = tag_keys.get(block_key)
        if not dictionary:
            continue

        scoped_tags = []
        for key, value in dictionary.items():
            if key in tag_array or value in tag_array:
                scoped_tags.append(key)

        if scoped_tags:
            scopes.append((block_key, scoped_tags))

    return scopes

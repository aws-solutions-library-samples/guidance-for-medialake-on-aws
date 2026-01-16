"""
XMP segment parser - Adobe XMP (Extensible Metadata Platform)

XMP is XML-based metadata that can store rich information about images.
It can be embedded in JPEG APP1 segments, PNG iTXt chunks, or TIFF tags.

XMP can be split across multiple segments (XMP Extended) for large metadata.

Reference: https://www.adobe.com/devnet/xmp.html
"""

import re

from ..parser import AppSegmentParserBase
from ..plugins import segment_parsers
from ..util.helpers import undefined_if_empty

# XMP headers in different formats
XMP_CORE_HEADER = "http://ns.adobe.com/"
XMP_MAIN_HEADER = "http://ns.adobe.com/xap/1.0/"
XMP_EXTENDED_HEADER = "http://ns.adobe.com/xmp/extension/"

# Length constants
TIFF_HEADER_LENGTH = 4  # 2 bytes for markers + 2 bytes length
XMP_EXTENDED_DATA_OFFSET = 79  # Extended XMP has guid, length, offset in header


class Xmp(AppSegmentParserBase):
    """Parser for Adobe XMP metadata"""

    type = "xmp"
    multi_segment = True

    @staticmethod
    def can_handle(chunk, offset, length):
        """
        Check if this is an XMP segment

        XMP segments start with 'http' and Adobe namespace URL

        Args:
            chunk: BufferView of file data
            offset: Offset to check
            length: Segment length

        Returns:
            bool: True if this is XMP
        """
        return (
            chunk.get_uint8(offset + 1) == 0xE1
            and chunk.get_uint32(offset + 4) == 0x68747470  # 'http'
            and chunk.get_string(offset + 4, len(XMP_CORE_HEADER)) == XMP_CORE_HEADER
        )

    @staticmethod
    def header_length(chunk, offset, length=None):
        """
        Determine XMP header length (main vs extended)

        Args:
            chunk: BufferView of file data
            offset: Offset of segment
            length: Segment length (unused but required for compatibility)

        Returns:
            int: Header length in bytes
        """
        header_string = chunk.get_string(offset + 4, len(XMP_EXTENDED_HEADER))
        if header_string == XMP_EXTENDED_HEADER:
            return XMP_EXTENDED_DATA_OFFSET
        else:
            # Main XMP: TIFF header + main header + null terminator
            return TIFF_HEADER_LENGTH + len(XMP_MAIN_HEADER) + 1

    @staticmethod
    def find_position(chunk, offset):
        """
        Find XMP segment position and handle multi-segment detection

        Args:
            chunk: BufferView of file data
            offset: Offset to start from

        Returns:
            dict: Segment information
        """
        # Call the base class method but with XMP class to get correct header_length
        seg = super(Xmp, Xmp).find_position(chunk, offset)

        # Determine if this is main or extended XMP
        seg["multi_segment"] = seg["extended"] = (
            seg["headerLength"] == XMP_EXTENDED_DATA_OFFSET
        )

        if seg["multi_segment"]:
            # Extended XMP segments are numbered
            seg["chunk_count"] = chunk.get_uint8(offset + 72)
            seg["chunk_number"] = chunk.get_uint8(offset + 76)
            # Also set camelCase versions for JPEG parser compatibility
            seg["chunkCount"] = seg["chunk_count"]
            seg["chunkNumber"] = seg["chunk_number"]
            # First and second chunk both have 0 as chunk number
            # The true first chunk (with <x:xmpmeta) has zeroes in last two bytes
            if chunk.get_uint8(offset + 77) != 0:
                seg["chunk_number"] += 1
                seg["chunkNumber"] = seg["chunk_number"]
        else:
            # Main XMP - treat as single complete segment
            # We can't determine if there are extended chunks without parsing,
            # but for now assume it's complete
            seg["chunk_count"] = 1
            seg["chunk_number"] = 0
            # Also set camelCase versions for JPEG parser compatibility
            seg["chunkCount"] = seg["chunk_count"]
            seg["chunkNumber"] = seg["chunk_number"]

        return seg

    @staticmethod
    def handle_multi_segments(all_segments):
        """
        Combine multiple XMP segments into one string

        Args:
            all_segments: List of segment dicts

        Returns:
            str: Combined XMP string
        """
        return "".join(
            seg["chunk"].get_string(0, seg["chunk"].byte_length) for seg in all_segments
        )

    def normalize_input(self, input_data):
        """
        Normalize XMP input to string

        XMP as IFD0 tag in TIFF can be either bytes or string.

        Args:
            input_data: Either string or bytes

        Returns:
            str: XMP as string
        """
        if isinstance(input_data, str):
            return input_data
        elif hasattr(input_data, "_data"):
            # This is a BufferView object - get the underlying data
            buffer_view = input_data
            data = buffer_view.get_string(0, buffer_view.byte_length)
            return data
        else:
            # Convert bytes to string, handling potential encoding issues
            try:
                return input_data.decode("utf-8")
            except UnicodeDecodeError:
                return input_data.decode("utf-8", errors="ignore")

    def parse(self, xmp_string=None):
        """
        Parse XMP XML metadata

        Args:
            xmp_string: XMP XML string (defaults to self.chunk)

        Returns:
            dict or str: Parsed XMP as dict, or raw string if parse=False
        """
        if xmp_string is None:
            xmp_string = self.chunk

        if not self.local_options.parse:
            return xmp_string

        # Add IDs to nested tags for proper parsing
        xmp_string = id_nested_tags(xmp_string)

        # Find all rdf:Description tags
        tags = XmlTag.find_all(xmp_string, "rdf", "Description")
        if len(tags) == 0:
            tags.append(XmlTag("rdf", "Description", None, xmp_string))

        # Parse all properties into namespaced objects
        xmp = {}
        for tag in tags:
            for prop in tag.properties:
                namespace = get_namespace(prop.ns, xmp)
                assign_to_object(prop, namespace)

        return prune_object(xmp)

    def assign_to_output(self, root, xmp):
        """
        Assign parsed XMP to output

        XMP namespaces are handled specially:
        - 'tiff' namespace merges into ifd0
        - 'exif' namespace merges into exif
        - Other namespaces are assigned directly

        Args:
            root: Output root object
            xmp: Parsed XMP data
        """
        if not self.local_options.parse:
            # XMP not parsed - include raw string
            root["xmp"] = xmp
        else:
            # Parsed XMP - merge namespaces appropriately
            # Handle case where xmp is None (empty or invalid XMP)
            if xmp is not None and isinstance(xmp, dict):
                for ns, ns_object in xmp.items():
                    if ns == "tiff":
                        self.assign_object_to_output(root, "ifd0", ns_object)
                    elif ns == "exif":
                        self.assign_object_to_output(root, "exif", ns_object)
                    elif ns == "xmlns":
                        # XMLNS attributes are namespace identifiers - not useful
                        pass
                    else:
                        self.assign_object_to_output(root, ns, ns_object)


def prune_object(obj):
    """
    Remove undefined properties and empty objects

    Args:
        obj: Object to prune

    Returns:
        dict or None: Pruned object or None if empty
    """
    if not isinstance(obj, dict):
        return obj

    for key in list(obj.keys()):
        val = undefined_if_empty(obj[key])
        if val is None:
            del obj[key]
        else:
            obj[key] = val

    return undefined_if_empty(obj)


# Register XMP segment parser
segment_parsers["xmp"] = Xmp


# ----- XML PARSING CLASSES -----


class XmlAttr:
    """XML attribute (e.g., ns:name="value")"""

    @staticmethod
    def find_all(string):
        """
        Find all XML attributes in string

        Args:
            string: XML string to search

        Returns:
            list: List of XmlAttr objects
        """
        if not string:
            return []

        # Match ns:name="value" or ns:name='value'
        regex = re.compile(
            r'([a-zA-Z0-9\-]+):([a-zA-Z0-9\-]+)=("[^"]*"|\'[^\']*\')', re.MULTILINE
        )
        matches = regex.findall(string)
        return [XmlAttr.unpack_match(match) for match in matches]

    @staticmethod
    def unpack_match(match):
        """
        Unpack regex match into XmlAttr

        Args:
            match: Regex match tuple (ns, name, value)

        Returns:
            XmlAttr: Attribute object
        """
        ns, name, value = match
        value = value[1:-1]  # Remove quotes
        value = normalize_value(value)
        return XmlAttr(ns, name, value)

    def __init__(self, ns, name, value):
        """
        Initialize XML attribute

        Args:
            ns: Namespace
            name: Attribute name
            value: Attribute value
        """
        self.ns = ns
        self.name = name
        self.value = value

    def serialize(self):
        """Serialize attribute to value"""
        return self.value


class XmlTag:
    """XML tag (e.g., <ns:name>...</ns:name>)"""

    TAG_NAME_PART_REGEX = r"[\w\d\-]+"
    VALUE_PROP = "value"

    @staticmethod
    def find_all(xmp_string, ns=None, name=None):
        """
        Find all XML tags matching namespace and name

        Args:
            xmp_string: XML string to search
            ns: Namespace to match (or None for any)
            name: Tag name to match (or None for any)

        Returns:
            list: List of XmlTag objects
        """
        if not xmp_string:
            return []

        # Build regex based on what we're searching for
        if ns is not None or name is not None:
            ns_pattern = ns or XmlTag.TAG_NAME_PART_REGEX
            name_pattern = name or XmlTag.TAG_NAME_PART_REGEX
            regex = re.compile(
                rf'<({ns_pattern}):({name_pattern})(#\d+)?((\s+?[\w\d\-:]+=("[^"]*"|\'[^\']*\'))*\s*)(\/>|>([\s\S]*?)<\/\1:\2(?:#\d+)?>)',
                re.MULTILINE,
            )
        else:
            regex = re.compile(
                r'<([\w\d\-]+):([\w\d\-]+)(#\d+)?((\s+?[\w\d\-:]+=("[^"]*"|\'[^\']*\'))*\s*)(\/>|>([\s\S]*?)<\/\1:\2(?:#\d+)?>)',
                re.MULTILINE,
            )

        matches = regex.findall(xmp_string)
        return [XmlTag.unpack_match(match) for match in matches]

    @staticmethod
    def unpack_match(match):
        """
        Unpack regex match into XmlTag

        Args:
            match: Regex match tuple

        Returns:
            XmlTag: Tag object
        """
        ns = match[0]
        name = match[1]
        attr_string = match[3]
        inner_xml = match[7] if len(match) > 7 else None
        return XmlTag(ns, name, attr_string, inner_xml)

    def __init__(self, ns, name, attr_string, inner_xml):
        """
        Initialize XML tag

        Args:
            ns: Namespace
            name: Tag name
            attr_string: Attribute string
            inner_xml: Inner XML content
        """
        self.ns = ns
        self.name = name
        self.attr_string = attr_string
        self.inner_xml = inner_xml
        self.attrs = XmlAttr.find_all(attr_string) if attr_string else []
        self.children = XmlTag.find_all(inner_xml) if inner_xml else []
        self.value = (
            normalize_value(inner_xml)
            if (inner_xml and len(self.children) == 0)
            else None
        )
        self.properties = self.attrs + self.children

    @property
    def is_primitive(self):
        """Check if tag is primitive (has value, no attrs/children)"""
        return (
            self.value is not None and len(self.attrs) == 0 and len(self.children) == 0
        )

    @property
    def is_list_container(self):
        """Check if tag contains a single list child"""
        return len(self.children) == 1 and self.children[0].is_list

    @property
    def is_list(self):
        """Check if tag is a list (rdf:Seq, rdf:Bag, rdf:Alt)"""
        return self.ns == "rdf" and self.name in ("Seq", "Bag", "Alt")

    @property
    def is_list_item(self):
        """Check if tag is a list item (rdf:li)"""
        return self.ns == "rdf" and self.name == "li"

    def serialize(self):
        """
        Serialize tag to Python object

        Returns:
            Various: Primitive value, list, dict, or None
        """
        # Invalid/undefined
        if len(self.properties) == 0 and self.value is None:
            return None

        # Primitive property
        if self.is_primitive:
            return self.value

        # Tag containing list <ns:tag><rdf:Seq>...</rdf:Seq></ns:tag>
        if self.is_list_container:
            return self.children[0].serialize()

        # List tag itself <rdf:Seq>...</rdf:Seq>
        if self.is_list:
            return unwrap_array([child.serialize() for child in self.children])

        # <rdf:li> may have single object-tag child
        if self.is_list_item and len(self.children) == 1 and len(self.attrs) == 0:
            return self.children[0].serialize()

        # Process attributes and children into object
        output = {}
        for prop in self.properties:
            assign_to_object(prop, output)

        if self.value is not None:
            output[self.VALUE_PROP] = self.value

        return undefined_if_empty(output)


# ----- UTILITY FUNCTIONS -----


def assign_to_object(prop, target):
    """
    Assign property to target object

    Args:
        prop: Property with serialize() method
        target: Target dict
    """
    serialized = prop.serialize()
    if serialized is not None:
        target[prop.name] = serialized


def unwrap_array(array):
    """Unwrap single-item arrays"""
    return array[0] if len(array) == 1 else array


def get_namespace(ns, root):
    """Get or create namespace in root object"""
    if ns not in root:
        root[ns] = {}
    return root[ns]


def normalize_value(value):
    """
    Normalize XML value to Python type

    Args:
        value: String value

    Returns:
        Various: Number, bool, string, or None
    """
    if is_undefinable(value):
        return None

    # Try to parse as number
    try:
        num = float(value)
        # Return int if it's a whole number
        if num.is_integer():
            return int(num)
        return num
    except (ValueError, AttributeError):
        pass

    # Try to parse as boolean
    lowercase = value.lower()
    if lowercase == "true":
        return True
    if lowercase == "false":
        return False

    return value.strip()


def is_undefinable(value):
    """Check if value should be treated as undefined"""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    return value in ("null", "undefined", "") or value.strip() == ""


# Tags that need IDs when nested (for proper parsing)
IDENTIFIABLE_TAGS = [
    "rdf:li",
    "rdf:Seq",
    "rdf:Bag",
    "rdf:Alt",
    "rdf:Description",  # Special case for nested descriptions in list items
]


def id_nested_tags(xmp_string):
    """
    Add unique IDs to nested tags for proper parsing

    When XMP has nested lists or descriptions, we need to track
    opening/closing tags properly. This adds #ID to matching pairs.

    Example:
        <rdf:li> -> <rdf:li#1>
        </rdf:li> -> </rdf:li#1>

    Args:
        xmp_string: XMP XML string

    Returns:
        str: XMP with ID'd tags
    """
    stacks = {tag: [] for tag in IDENTIFIABLE_TAGS}
    counts = {tag: 0 for tag in IDENTIFIABLE_TAGS}

    # Build regex pattern
    tags_pattern = "|".join(re.escape(tag) for tag in IDENTIFIABLE_TAGS)
    regex = re.compile(rf"(<|\/)({tags_pattern})")

    def replacer(match):
        prev_char = match.group(1)
        tag = match.group(2)

        if prev_char == "<":
            # Opening tag
            counts[tag] += 1
            tag_id = counts[tag]
            stacks[tag].append(tag_id)
            return f"{match.group(0)}#{tag_id}"
        else:
            # Closing tag
            tag_id = stacks[tag].pop()
            return f"{match.group(0)}#{tag_id}"

    return regex.sub(replacer, xmp_string)

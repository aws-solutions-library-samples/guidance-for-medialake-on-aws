"""
SVG metadata extraction utilities.

This module provides functions for extracting metadata from SVG files
by parsing their XML structure.
"""

from typing import Optional

from lxml import etree


async def extract_svg_metadata(buffer: bytes) -> Optional[dict]:
    """
    Extract metadata from SVG XML structure.

    Parses the SVG file as XML and extracts the metadata element
    from the svg root element. Returns None if parsing fails or
    if no metadata is present.

    Args:
        buffer: SVG file bytes

    Returns:
        dict: SVG metadata or None if not found/error

    Examples:
        >>> svg_content = b'''<?xml version="1.0"?>
        ... <svg xmlns="http://www.w3.org/2000/svg">
        ...   <metadata>
        ...     <title>My Image</title>
        ...     <author>John Doe</author>
        ...   </metadata>
        ... </svg>'''
        >>> await extract_svg_metadata(svg_content)
        {'title': 'My Image', 'author': 'John Doe'}

        >>> svg_no_metadata = b'<svg></svg>'
        >>> await extract_svg_metadata(svg_no_metadata)
        None
    """
    try:
        # Parse the XML content
        root = etree.fromstring(buffer)

        # Define SVG namespace (most SVG files use this)
        namespaces = {
            "svg": "http://www.w3.org/2000/svg",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "dc": "http://purl.org/dc/elements/1.1/",
            "cc": "http://creativecommons.org/ns#",
        }

        # Try to find metadata element with namespace
        metadata_elem = root.find(".//svg:metadata", namespaces)

        # If not found with namespace, try without namespace
        if metadata_elem is None:
            metadata_elem = root.find(".//metadata")

        # If still not found, return None
        if metadata_elem is None:
            return None

        # Extract metadata from the element
        metadata_dict = {}

        # Recursively extract all child elements and their text content
        def extract_element_data(elem, parent_key=""):
            """Recursively extract data from XML element."""
            # Get the tag name without namespace
            tag = elem.tag
            if "}" in tag:
                tag = tag.split("}")[1]

            # Build the key
            key = f"{parent_key}.{tag}" if parent_key else tag

            # If element has text content and no children, store it
            if elem.text and elem.text.strip() and len(elem) == 0:
                metadata_dict[key] = elem.text.strip()

            # If element has attributes, store them
            for attr_name, attr_value in elem.attrib.items():
                # Remove namespace from attribute name
                if "}" in attr_name:
                    attr_name = attr_name.split("}")[1]
                metadata_dict[f"{key}.{attr_name}"] = attr_value

            # Recursively process children
            for child in elem:
                extract_element_data(child, key)

        # Extract all data from metadata element's children
        for child in metadata_elem:
            extract_element_data(child)

        # If no metadata was extracted, return None
        if not metadata_dict:
            return None

        return metadata_dict

    except etree.XMLSyntaxError:
        # XML parsing failed
        return None
    except Exception:
        # Any other error during parsing
        return None

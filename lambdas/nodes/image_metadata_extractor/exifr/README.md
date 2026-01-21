# exifr-py

📷 Python port of the fastest and most versatile JavaScript EXIF reading library.

## Features

* 🏎️ **Fast EXIF parsing**: Optimized performance
* 🗃️ **Any input**: File paths, URLs, bytes, file objects
* 📷 Files: **.jpg**, **.tif**, **.png**, **.heic**, .avif
* 🔎 Segments: **TIFF** (EXIF, GPS), **XMP**, **ICC**, **IPTC**, JFIF, IHDR
* 📑 **Reads only necessary bytes**
* 🔬 **Selective tag parsing**
* 🖼️ Extracts thumbnails
* 💔 Salvages broken files
* 🧩 Modular architecture
* 📚 Customizable tag dictionaries

## Installation

```bash
pip install exifr
```

## Quick Start

```python
import exifr

# Parse EXIF from a file
data = exifr.parse('photo.jpg')
print(f"Camera: {data.get('Make')} {data.get('Model')}")

# Extract GPS coordinates
coords = exifr.gps('photo.jpg')
print(f"Location: {coords['latitude']}, {coords['longitude']}")

# Get orientation
orientation = exifr.orientation('photo.jpg')

# Extract thumbnail
thumbnail_bytes = exifr.thumbnail('photo.jpg')
```

## Usage

### Basic parsing

```python
import exifr

# Parse all default segments (IFD0, EXIF, GPS)
data = exifr.parse('photo.jpg')

# Parse everything
data = exifr.parse('photo.jpg', True)

# Parse only specific tags
data = exifr.parse('photo.jpg', ['Model', 'FNumber', 'ISO'])

# Custom options
data = exifr.parse('photo.jpg', {
    'ifd0': False,
    'exif': True,
    'gps': True,
    'xmp': True
})
```

### GPS coordinates

```python
coords = exifr.gps('photo.jpg')
# Returns: {'latitude': 50.29960, 'longitude': 14.12345}
```

### Orientation

```python
# Get numeric orientation (1-8)
orientation = exifr.orientation('photo.jpg')

# Get rotation info
rotation = exifr.rotation('photo.jpg')
# Returns: {'deg': 90, 'rad': 1.5708, 'scaleX': 1, 'scaleY': 1, 'dimensionSwapped': True}
```

### Thumbnail extraction

```python
thumbnail = exifr.thumbnail('photo.jpg')
# Returns bytes of embedded thumbnail
```

## API Reference

### `parse(file, options=None)`

Main parsing function. Returns dictionary of EXIF data.

**Parameters:**
- `file`: File path (str), URL (str), bytes, or file-like object
- `options`: None, True, list of tags, or dict of options

**Options dict:**
```python
{
    # Segments
    'tiff': True,
    'xmp': False,
    'icc': False,
    'iptc': False,
    'jfif': False,
    'ihdr': False,  # PNG only

    # TIFF blocks
    'ifd0': True,
    'ifd1': False,
    'exif': True,
    'gps': True,
    'interop': False,

    # Notable tags
    'makerNote': False,
    'userComment': False,

    # Filters
    'pick': [],  # Only parse these tags
    'skip': [],  # Skip these tags

    # Formatters
    'translateKeys': True,
    'translateValues': True,
    'reviveValues': True,
    'sanitize': True,
    'mergeOutput': True,
    'silentErrors': True,

    # Chunked reading
    'chunked': True,
    'firstChunkSize': 65536,
    'chunkSize': 65536,
    'chunkLimit': 5,
}
```

### `gps(file)`

Extract only GPS coordinates. Returns dict with `latitude` and `longitude`.

### `orientation(file)`

Extract only orientation tag. Returns int (1-8).

### `rotation(file)`

Extract rotation information. Returns dict with rotation details.

### `thumbnail(file)`

Extract embedded thumbnail. Returns bytes or None.

## License

MIT License - Ported from [exifr](https://github.com/MikeKovarik/exifr) by Mike Kovařík

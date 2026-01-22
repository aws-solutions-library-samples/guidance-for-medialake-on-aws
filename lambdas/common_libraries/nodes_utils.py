def generate_derived_filename(original_key: str, suffix: str, output_ext: str) -> str:
    """
    Generate a unique derived filename that includes the original extension
    to prevent naming collisions when files have the same base name but different extensions.

    Args:
        original_key: Original S3 key (e.g., "path/to/nature.png")
        suffix: Suffix to append (e.g., "thumbnail", "proxy", "waveform")
        output_ext: Output file extension without dot (e.g., "png", "jpg", "mp4")

    Returns:
        New key with original extension embedded (e.g., "path/to/nature-png_thumbnail.png")

    Examples:
        generate_derived_filename("nature.png", "thumbnail", "png")
            → "nature-png_thumbnail.png"
        generate_derived_filename("path/to/video.mp4", "proxy", "mp4")
            → "path/to/video-mp4_proxy.mp4"
        generate_derived_filename("audio.wav", "waveform", "png")
            → "audio-wav_waveform.png"
    """
    # Split path and filename
    if "/" in original_key:
        path_prefix = original_key.rsplit("/", 1)[0] + "/"
        filename = original_key.rsplit("/", 1)[1]
    else:
        path_prefix = ""
        filename = original_key

    # Extract base name and original extension
    if "." in filename:
        base_name, orig_ext = filename.rsplit(".", 1)
        orig_ext = orig_ext.lower()
    else:
        base_name = filename
        orig_ext = "unknown"

    # Build new filename: basename-originalext_suffix.outputext
    new_filename = f"{base_name}-{orig_ext}_{suffix}.{output_ext}"

    return f"{path_prefix}{new_filename}"


def seconds_to_smpte(total_seconds, fps=30):
    """
    Convert seconds to SMPTE timecode format (HH:MM:SS:FF).

    Args:
        total_seconds (float): Time in seconds
        fps (int): Frames per second, defaults to 24

    Returns:
        str: SMPTE timecode string
    """
    # Calculate hours, minutes, and seconds
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)

    # Calculate frames using the fractional part of the seconds
    frames = int(round((total_seconds - int(total_seconds)) * fps))

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def format_duration(seconds):
    """
    Format duration in seconds to a human-readable string (HH:MM:SS).

    Args:
        seconds (float): Duration in seconds

    Returns:
        str: Formatted duration string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

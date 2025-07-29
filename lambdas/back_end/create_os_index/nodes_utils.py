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

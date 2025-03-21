def seconds_to_smpte(total_seconds, fps=24):
    # Calculate hours, minutes, and seconds
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    
    # Calculate frames using the fractional part of the seconds
    frames = int(round((total_seconds - int(total_seconds)) * fps))
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


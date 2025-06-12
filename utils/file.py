def read_file_content(path: str) -> str:
    """Reads the entire content of a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found at {path}")
    except Exception as e:
        raise IOError(f"Error reading file {path}: {e}")

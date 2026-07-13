import io

import pillow_heif
from PIL import Image

_MAX_DIMENSION = 1920


class TranscodeError(Exception):
    pass


def transcode_heic_to_jpeg(data: bytes) -> bytes:
    try:
        heif_file = pillow_heif.read_heif(data)
        raw_data = bytes(heif_file.data) if heif_file.data is not None else b""
        image = Image.frombytes(heif_file.mode, heif_file.size, raw_data, "raw")
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        raise TranscodeError(f"HEIC transcoding failed: {e}") from e


def compress_to_limit(data: bytes, max_bytes: int) -> bytes:
    """Compress a JPEG/PNG image to fit within max_bytes.

    Caps resolution at _MAX_DIMENSION on the longest side first, then
    iterates JPEG quality downward (85 → 75 → 60 → 40) until the result
    fits. Returns the original bytes unchanged if already within the limit.
    """
    if len(data) <= max_bytes:
        return data

    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        raise TranscodeError(f"Could not open image for compression: {e}") from e

    # Resize if largest dimension exceeds the cap
    w, h = image.size
    if max(w, h) > _MAX_DIMENSION:
        scale = _MAX_DIMENSION / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    for quality in (85, 75, 60, 40):
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality, optimize=True)
        result = buf.getvalue()
        if len(result) <= max_bytes:
            return result

    # Last resort: very aggressive resize + lowest quality
    image = image.resize((image.width // 2, image.height // 2), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=30, optimize=True)
    return buf.getvalue()

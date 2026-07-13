import io

import pillow_heif
from PIL import Image


class TranscodeError(Exception):
    pass


def transcode_heic_to_jpeg(data: bytes) -> bytes:
    try:
        heif_file = pillow_heif.read_heif(data)
        image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        raise TranscodeError(f"HEIC transcoding failed: {e}") from e

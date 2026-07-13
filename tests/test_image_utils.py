"""Tests for src/utils/image.py"""

from unittest.mock import MagicMock, patch

import pytest

from src.utils.image import TranscodeError, transcode_heic_to_jpeg


def test_transcode_heic_calls_pillow_heif():
    fake_heif = MagicMock()
    fake_heif.mode = "RGB"
    fake_heif.size = (2, 2)
    fake_heif.data = b"\xff\x00\x00" * 4  # 4 pixels, 3 bytes each

    with (
        patch("src.utils.image.pillow_heif.read_heif", return_value=fake_heif) as mock_read,
        patch("src.utils.image.Image.frombytes") as mock_frombytes,
    ):
        fake_img = MagicMock()
        mock_frombytes.return_value = fake_img

        def fake_save(buf, **kwargs):
            buf.write(b"\xff\xd8\xff")  # minimal JPEG magic bytes

        fake_img.save.side_effect = fake_save

        result = transcode_heic_to_jpeg(b"fake-heic-data")

    mock_read.assert_called_once_with(b"fake-heic-data")
    assert isinstance(result, bytes)


def test_transcode_failure_raises_transcode_error():
    with patch("src.utils.image.pillow_heif.read_heif", side_effect=RuntimeError("corrupt")):
        with pytest.raises(TranscodeError, match="HEIC transcoding failed"):
            transcode_heic_to_jpeg(b"bad-data")

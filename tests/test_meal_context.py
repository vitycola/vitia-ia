import pytest

from src.domain.meal_context import MEAL_CONTEXT_MAX_LEN, normalize_meal_context


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   \n\t ", None),
        ("\x00\x07\x1b", None),
        ("  200g rice  ", "200g rice"),
        ("rice\x00 and beans", "rice and beans"),
        ("rice\nchicken", "rice chicken"),
        ("a\r\nb", "a b"),
        ("a\x0bb", "a b"),
        ("a\x0cb", "a b"),
    ],
)
def test_normalize_cleans_input(raw, expected):
    assert normalize_meal_context(raw) == expected


def test_max_len_constant():
    assert MEAL_CONTEXT_MAX_LEN == 150


def test_exactly_150_unchanged():
    text = "a" * 150
    assert normalize_meal_context(text) == text


def test_151_truncated_to_150():
    assert normalize_meal_context("a" * 151) == "a" * 150


def test_300_keeps_first_150():
    text = "".join(chr(ord("a") + i % 26) for i in range(300))
    assert normalize_meal_context(text) == text[:150]


def test_truncation_leaving_trailing_space_is_rstripped():
    text = "a" * 149 + " " + "b" * 10
    assert normalize_meal_context(text) == "a" * 149

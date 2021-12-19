import pytest
from hypothesis import given
from hypothesis.strategies import from_regex

from miteclock.config import APIKey, load_api_key


@pytest.mark.parametrize("ws", ["{}", "{}\n", "\n{}\n"])
@given(content=from_regex(r"^[0-9a-fA-F]{16}$"))
def test_api_key_value(content, ws):
    """Hexadecimal keys of the right length should work.

    Surrounding whitespace doesn't matter, upper/lower case also.
    """
    assert str(APIKey.parse_obj(ws.format(content))) == content.strip().lower()


def key_prompt(key_value):
    def prompter(prompt_msg):
        print(prompt_msg, end="")
        return key_value

    return prompter


def test_load_api_key_success(tmp_path, capsys):
    """File with api key is present and contains reasonable data."""
    apikey_pth = tmp_path / "apikey"
    apikey_pth.write_text("6d12e0bf974df0e9\n")
    assert (
        load_api_key(apikey_pth, prompt=key_prompt("6d12e0bf974df0e9"))
        == "6d12e0bf974df0e9"
    )
    out, _ = capsys.readouterr()
    assert out == ""


@pytest.mark.parametrize("contents", ("", "abc\ndef", "abracadabra", "abcefghijk"))
def test_load_api_key_invalid(contents, tmp_path, capsys):
    """Make sure the value for the key is valid."""
    apikey_pth = tmp_path / "apikey"
    apikey_pth.write_text(contents)
    assert (
        load_api_key(apikey_pth, prompt=key_prompt("6d12e0bf974df0e9"))
        == "6d12e0bf974df0e9"
    )
    out, _ = capsys.readouterr()
    assert out == "Found key but it is invalid, please enter it again"


def test_load_api_key_file_missing(tmp_path, capsys):

    assert (
        load_api_key(tmp_path / "apikey", prompt=key_prompt("6d12e0bf974df0e9"))
        == "6d12e0bf974df0e9"
    )
    out, _ = capsys.readouterr()
    assert out == "Key not found, please enter it"

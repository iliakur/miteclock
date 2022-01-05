import re

import pytest
from hypothesis import given
from hypothesis.strategies import from_regex

from miteclock.config import (
    ApiKey,
    Config,
    SettingsLoadError,
    load_api_key,
    load_config,
    to_toml,
)


@pytest.mark.parametrize("ws", ["{}", "{}\n", "\n{}\n"])
@given(raw=from_regex(re.compile(r"^[0-9a-f]{16}$", re.IGNORECASE)))
def test_api_key_valid(raw, ws):
    """Hexadecimal keys of the right length should work.

    Surrounding whitespace doesn't matter, upper/lower case also.
    """
    assert str(ApiKey(ws.format(raw))) == raw.strip().lower()


@pytest.mark.parametrize("ws", ["{}", "{}\n", "\n{}\n"])
@given(
    raw=from_regex(re.compile(r"^[0-9a-f]{,15}$", re.IGNORECASE))  # Too short.
    | from_regex(re.compile(r"^[0-9a-f]{17,}$", re.IGNORECASE))  # Too long.
    | from_regex(re.compile(r"[^0-9a-f]+", re.IGNORECASE))  # At least one non-hex char.
)
def test_api_key_invalid(raw, ws):
    """Make sure invalid inputs do fail."""
    with pytest.raises(ValueError):
        ApiKey(ws.format(raw))


def prompt_for_testing(ret_value):
    def prompter(prompt_msg):
        print(prompt_msg, end="")
        return ret_value

    return prompter


def test_load_api_key_success(tmp_path, capsys):
    """File with api key is present and contains reasonable data."""
    apikey_pth = tmp_path / "apikey"
    key_val = "6d12e0bf974df0e9\n"
    apikey_pth.write_text(key_val)
    assert (
        str(load_api_key(apikey_pth, prompt=prompt_for_testing("6d12e0bf974df0e9")))
        == "6d12e0bf974df0e9"
    )
    out, _ = capsys.readouterr()
    assert out == ""
    assert apikey_pth.read_text() == key_val


def test_load_api_key_file_missing(tmp_path, capsys):
    """Handle missing api key file.

    We should prompt user for the key and add the file.
    """
    key_val = "6d12e0bf974df0e9"
    apikey_path = tmp_path / "apikey"
    assert str(load_api_key(apikey_path, prompt=prompt_for_testing(key_val))) == key_val
    out, _ = capsys.readouterr()
    assert out == "Key not found, please enter it."
    assert apikey_path.read_text() == key_val + "\n"


@pytest.mark.parametrize(
    "key, errmsg",
    [
        ("abc", "API key must be exactly 16 characters long, this one is 3."),
        ("6p12e0bf974df0e9", "API key must only consist of hexadecimal characters."),
    ],
)
def test_load_api_key_invalid(key, errmsg, tmp_path):
    """The key is missing, we prompt for it, user enters something invalid."""
    with pytest.raises(SettingsLoadError) as excinfo:
        load_api_key(tmp_path / "apikey", prompt_for_testing(key))
    assert str(excinfo.value) == errmsg


def test_default_toml_content():
    """Toml content for the default config."""
    url = "https://abc.mite.yo.lk"
    assert to_toml(Config(url=url)) == (
        f'url = "{url}"\n'
        'menu_keys = "asdfjkl;"\n\n'
        "[shortcuts] # Add your shortcuts inside this section.\n"
    )


def test_load_config_does_not_exist(conf_path, capsys):
    """Handle missing config file.

    Prompt for mandatory information and use it to instantiate the current config type.
    """
    config = load_config(
        conf_path,
        prompt=prompt_for_testing("https://abc.mite.yo.lk"),
    )
    assert config == Config(
        url="https://abc.mite.yo.lk", menu_keys="asdfjkl;", shortcuts={}
    )
    out, _ = capsys.readouterr()
    assert out == "Please copy/paste your mite URL: "


def test_load_config_does_not_exist_invalid_url_input(conf_path, capsys):
    """Config file is missing and user provides invalid mite URL.

    We throw an exception, assuming that we will prompt again for it next time.
    """
    with pytest.raises(SettingsLoadError) as excinfo:
        load_config(
            conf_path,
            prompt=prompt_for_testing("http://abc.mite.yo.lk"),
        )
    assert str(excinfo.value) == (
        "Detected the following problems with your configuration:\n"
        "url: HTTPS is required for security."
    )
    out, _ = capsys.readouterr()
    assert out == "Please copy/paste your mite URL: "


@pytest.fixture
def conf_path(tmp_path):
    return tmp_path / "config.toml"


def test_duplicate_toml_keys(conf_path):
    """Duplicate keys are caught by toml parser, make sure we report them nicely."""
    conf_path.write_text('[shortcuts]\nm="test"\nm="another"')
    with pytest.raises(SettingsLoadError) as excinfo:
        load_config(conf_path)
    assert str(excinfo.value) == (
        'There was a problem parsing your configuration file: Key "m" already exists.'
    )


def test_load_config_toml_parse_error(conf_path):
    conf_path.write_text('a="valid"\nb=invalid\nc="valid"')
    with pytest.raises(SettingsLoadError) as excinfo:
        load_config(conf_path)
    assert str(excinfo.value) == (
        "There was a problem parsing your configuration file: "
        "Unexpected character: 'i' at line 2 col 2\n"
        "b=invalid\n"
        "  ^"
    )


def test_load_valid_config(conf_path):
    base_url = "https://abc.mite.yo.lk"
    conf_path.write_text(
        f'url="{base_url}"\n'
        'menu_keys="abc"\n\n'
        "[shortcuts]\n"
        'a="test"\nb="test2"\nc = ["a", "test3"]'
        '\nd = {"pattern"= "QA", "match"="strict"}'
    )
    config = load_config(conf_path)
    assert config == Config(
        base_url,
        menu_keys="abc",
        shortcuts={
            "a": "test",
            "b": "test2",
            "c": ["a", "test3"],
            "d": dict(pattern="QA", match="strict"),
        },
    )


def test_load_valid_legacy_config(conf_path):
    base_url = "https://abc.mite.yo.lk"
    conf_path.write_text(
        'account="abc"\n'
        'menu_keys="abc"\n\n'
        "[shortcuts]\n"
        'a="test"\nb="test2"\nc = ["a", "test3"]'
        '\nd = {"pattern"= "QA", "match"="strict"}'
    )
    config = load_config(conf_path)
    assert config == Config(
        url=base_url,
        menu_keys="abc",
        shortcuts={
            "a": "test",
            "b": "test2",
            "c": ["a", "test3"],
            "d": dict(pattern="QA", match="strict"),
        },
    )


def test_legacy_config(conf_path):
    """When config file has legacy structure, we should still return latest version."""
    conf_path.write_text(
        "\n".join(
            [
                'account="abc"',
                'menu_keys="abc"',
                "",
                "[shortcuts]",
            ]
        )
    )
    config = load_config(conf_path)
    assert config == Config(
        url="https://abc.mite.yo.lk",
        menu_keys="abc",
    )


@pytest.mark.parametrize(
    "url_path", ["/", "/daily", "/daily/#2021/12/26", "/#2021/12/26"]
)
def test_url_remove_path(url_path):
    """If we get any kind of path added to a URL we keep only the base."""
    base_url = "https://abc.mite.yo.lk"
    assert str(Config(url=base_url + url_path).url) == base_url


def test_non_mite_url():
    """Only mite urls are supported."""
    with pytest.raises(ValueError) as excinfo:
        Config(url="https://google.com")
    assert str(excinfo.value) == "url: Make sure you are using a mite url."


def test_no_menu_keys():
    """At least one menu key should be specified, otherwise we crash early."""
    with pytest.raises(ValueError) as excinfo:
        Config(url="https://abc.mite.yo.lk", menu_keys="")
    assert str(excinfo.value) == "menu_keys: At least one key must be provided."

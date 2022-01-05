"""Configuration."""
from __future__ import annotations

import os
import re
from functools import partial, singledispatch, wraps
from pathlib import Path
from typing import Callable, Dict, TypeVar
from urllib.parse import urlsplit, urlunsplit

import attrs
from tomlkit import document, dumps, loads, string, table
from tomlkit.exceptions import ParseError, TOMLKitError

from miteclock import __name__, __version__
from miteclock.activities import ShortcutData, validate_shortcuts
from miteclock.mite import StopWatch, init_api

# Follow $XDG_CONFIG_PATH specification.
CONFIG_ROOT = Path.home() / f".config/{__name__}"


def load_api_key(key_pth: Path, prompt: Callable[[str], str]) -> ApiKey:
    """Load API key from file.

    If it's missing or contains an invalid key, we ask user to enter the key again.
    """
    if key_pth.exists():
        raw, out_sink = key_pth.read_text(), os.devnull
    else:
        raw, out_sink = prompt("Key not found, please enter it"), key_pth
    try:
        key = ApiKey(raw)
    except ValueError as err:
        raise SettingsLoadError(str(err))
    with open(out_sink, mode="w") as fh:
        fh.write(f"{key}\n")
    return key


@attrs.frozen
class ApiKey:
    _value: str = attrs.field(converter=lambda v: v.strip().lower())

    @_value.validator
    def valid_key(self, attr: attrs.Attribute, value: str) -> None:
        if len(value) != 16:
            raise ValueError(
                f"API key must be exactly 16 characters long, this one is {len(value)}."
            )
        if not re.search(r"^[0-9a-f]+$", value):
            raise ValueError("API key must only consist of hexadecimal characters.")

    def __str__(self) -> str:
        return self._value


@attrs.define(frozen=True)
class Meta:
    """Create a namespace with information about the app, such as name and version."""

    name: str = __name__
    version: str = __version__
    config_dir: Path = CONFIG_ROOT


@attrs.frozen
class MiteSettings:
    """Settings related specifically to mite api."""

    api: Callable
    # Convenience wrapper since most of the requests are "GET".
    get: Callable
    stopwatch: StopWatch


@attrs.frozen
class Settings:
    """Settings combined from all the sources."""

    mite: MiteSettings
    menu_keys: str
    shortcuts: dict
    meta: Meta = Meta()


def initialize(prompt: Callable[[str], str]):
    """Try to load the settings from CONFIG_FILE.

    Execute the callback in case this runs into an error.
    """
    meta = Meta()
    key = load_api_key(CONFIG_ROOT / "apikey", prompt)
    config = load_config(CONFIG_ROOT / "config.toml", prompt)
    mite_api = init_api(str(config.url), str(key), meta.name, meta.version)

    return Settings(
        mite=MiteSettings(
            api=mite_api, get=partial(mite_api, "get"), stopwatch=StopWatch(mite_api)
        ),
        menu_keys=config.menu_keys,
        shortcuts=config.shortcuts,
        meta=meta,
    )


class SettingsLoadError(Exception):
    """Signals an unrecoverable error when loading configuration.

    Hides lower-level errors, such as parsing and validation, behind a simple interface
    that contains the message we should display to the user.
    """


@attrs.frozen
class MiteURL:
    scheme: str = attrs.field()
    host: str = attrs.field()

    @scheme.validator
    def only_https(self, attr: attrs.Attribute, val: str):
        if val != "https":
            raise ValueError("HTTPS is required for security.")

    @host.validator
    def mite_base_url(self, attr: attrs.Attribute, val: str):
        if not val.endswith("mite.yo.lk"):
            raise ValueError("Make sure you are using a mite url.")

    @classmethod
    def parse(cls, url: str) -> MiteURL:
        scheme, host, _, _, _ = urlsplit(url)
        return cls(scheme, host)

    def __str__(self) -> str:
        return urlunsplit((self.scheme, self.host, "", "", ""))


def _uniq_menu_keys(raw_keys: str) -> str:
    return "".join({k: None for k in raw_keys})


def _delay_url_validation(value: str) -> MiteURL:
    """Create mite url without validating it.

    This allows us to check it later as part of validating the whole config.
    """
    with attrs.validators.disabled():
        return MiteURL.parse(value)


T = TypeVar("T")
V = TypeVar("V")
C = TypeVar("C")


def _report_attr_name(
    validator: Callable[[C, attrs.Attribute, V], T]
) -> Callable[[C, attrs.Attribute, V], T]:
    """Wrap validator func to consistently report attr name in case of failure."""

    @wraps(validator)
    def inner(inst: C, attr: attrs.Attribute, value: V) -> T:
        try:
            return validator(inst, attr, value)
        except (TypeError, ValueError) as err:
            raise err.__class__(f"{attr.name}: {str(err)}")

    return inner


@attrs.frozen
class Config:
    """Contents of user's configuration file."""

    url = attrs.field(converter=_delay_url_validation)
    menu_keys: str = attrs.field(
        # For most people using QUERTY this is their home row.
        default="asdfjkl;",
        converter=_uniq_menu_keys,
        validator=attrs.validators.instance_of(str),
    )
    shortcuts: ShortcutData = attrs.field(factory=dict)

    @url.validator
    @_report_attr_name
    def valid_mite_url(self, attr: attrs.Attribute, value: MiteURL) -> None:
        attrs.validate(value)

    @menu_keys.validator
    @_report_attr_name
    def non_empty(self, attr: attrs.Attribute, value: str) -> None:
        if not value:
            raise ValueError("At least one key must be provided.")

    @shortcuts.validator
    @_report_attr_name
    def valid_shortcuts(self, attr: attrs.Attribute, value: ShortcutData) -> None:
        validate_shortcuts(value)


def to_toml(config: Config) -> str:
    """Generate toml-formatted content for configuration."""
    doc = document()
    doc.add("url", string(str(config.url)))
    doc.add("menu_keys", string(config.menu_keys))
    shortcuts = table()
    shortcuts.comment("Add your shortcuts inside this section.")
    doc.add("shortcuts", shortcuts)
    return dumps(doc)


def load_config(
    src: Path,
    prompt: Callable[[str], str] = input,
) -> Config:
    if not src.exists():
        config = _load_valid_config(url=prompt("Please copy/paste your mite URL"))
        src.write_text(to_toml(config))
        return config
    return _load_valid_config(**_parse_toml(src.read_text()))


def _load_valid_config(**kwargs) -> Config:
    try:
        return _convert_legacy(kwargs) if "account" in kwargs else Config(**kwargs)
    except (TypeError, ValueError) as err:
        raise SettingsLoadError(
            "Detected the following problems with your configuration:\n" + str(err)
        )


def _convert_legacy(parsed: Dict) -> Config:
    account = parsed.pop("account")
    return Config(url=f"https://{account}.mite.yo.lk", **parsed)


def _parse_toml(raw: str) -> Dict:
    try:
        return loads(raw)
    except TOMLKitError as err:
        raise SettingsLoadError((_explain_tomlkit_error(err, contents=raw)))


@singledispatch
def _explain_tomlkit_error(err: TOMLKitError, contents: str):
    _ = contents
    return "There was a problem parsing your configuration file: " + str(err)


@_explain_tomlkit_error.register
def _(err: ParseError, contents: str) -> str:
    problem_line = contents.split("\n")[err.line - 1]
    highlight_line = " " * err.col + "^"
    return "\n".join(
        [
            _explain_tomlkit_error.dispatch(TOMLKitError)(err, contents),
            problem_line,
            highlight_line,
        ]
    )

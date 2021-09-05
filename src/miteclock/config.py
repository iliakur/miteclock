"""Configuration."""
from dataclasses import asdict, dataclass, field
from functools import partial
from pathlib import Path
from typing import Callable

import toml

from miteclock import __name__, __version__
from miteclock.mite import StopWatch, init_api

# Follow $XDG_CONFIG_PATH specification.
CONFIG_ROOT = Path.home() / f".config/{__name__}"
CONFIG_FILE = CONFIG_ROOT / "config.toml"


@dataclass
class AppSettings:
    """Mostly for debugging/auditing, not really useful to most users."""

    name: str = __name__
    version: str = __version__
    config_dir: Path = CONFIG_ROOT
    initialized: bool = True


@dataclass
class MiteSettings:
    """Settings related specifically to mite api."""

    api: Callable
    # Convenience wrapper since most of the requests are "GET".
    get: Callable
    stopwatch: StopWatch


@dataclass
class Config:
    """This is actually read from configuration file."""

    account: str
    # For most people using QUERTY this is their home row.
    menu_keys: str = "asdfjkl;"
    shortcuts: dict = field(default_factory=dict)


@dataclass
class Settings:
    """Settings combined from all the sources."""

    mite: MiteSettings
    account: str
    menu_keys: str
    shortcuts: dict
    app: AppSettings = AppSettings()


def load_settings(initialize_account):
    """Try to load the settings from CONFIG_FILE.

    Execute the callback in case this runs into an error.
    """
    key_path = CONFIG_ROOT / "apikey"
    if not CONFIG_ROOT.exists():
        account, key = initialize_account()
        CONFIG_ROOT.mkdir(parents=True)
        with key_path.open("w") as fh:
            fh.write(key.strip())
        config = Config(account)
        with CONFIG_FILE.open("w") as confh:
            toml.dump(asdict(config), confh)

    # This is a bit inefficient in case we perform initialization,
    # but it's simpler and initialization only happens once.
    with key_path.open() as key_fh:
        key = key_fh.read().strip()
    with open(CONFIG_FILE) as conf_fh:
        config = Config(**toml.load(conf_fh))

    app = AppSettings()
    mite_api = init_api(config.account, key, app)

    return Settings(
        mite=MiteSettings(
            api=mite_api, get=partial(mite_api, "get"), stopwatch=StopWatch(mite_api)
        ),
        **asdict(config),
        app=app,
    )

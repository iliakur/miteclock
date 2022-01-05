try:
    from importlib.metadata import version
except ModuleNotFoundError:  # Python 3.7 uses backport package.
    from importlib_metadata import version
__version__ = version(__name__)

# Changelog

The version numbers follow a simple scheme: `<major>.<minor>`. Increments in major
version number signal changes that may be of interest to users. This mostly means new
features, because we make all efforts to avoid forcing users to change their
configuration. Once a command is added, we **never** remove it. Increments in minor
version signal code changes that do not require any attention from users.

## miteclock 2.1

- Refactor configuration loading to be more robust and capable at catching some invalid
  values.
- Misc improvements to tooling and code structure.

## miteclock 2.0

- Added short options for `m status --full/--short`.

## miteclock 1.1

- Change how currently tracked entry is highlighted in the list of all entries for the
  day.

## miteclock 1.0

After a year of use without any serious issues, the program is ready for version 1! This
release features the following changes:

### Features and Bugs

- Added `status` command to show current state of mite timer.
- Fixed a bug caused by us not trimming whitespace from an entry's note when comparing
  it to entries already present. This broke the idempotency guarantee when starting the
  clock for the same shortcut multiple times.

### Development Changes

- Switched to `src`-based layout, per recommended current practice.
- Updated dependencies and dropped python 3.6 support.
- Added backoff and timeouts to mite API requests.
- Increased test coverage.

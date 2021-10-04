# Changelog

The version numbers follow a simple scheme: `<major>.<minor>`. Increments in major
version number signal a change in the user interface. This means the users will likely
have to adjust their config files or read up on changes to command names and their
options. Increments in minor version signal code changes that do not require any
adjustments from the users.

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

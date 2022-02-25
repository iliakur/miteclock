# Changelog

The version numbers follow [CalVer](https://calver.org/). The **first number** is the
(short) year. The **second number** is incremented with each release starting at `1` for
each year. We make all efforts to maintain backwards-compatibility when it comes to the
configuration and the command-line interface. Breaking changes that are unavoidable will
be announced ahead of time and rolled out gradually.

## miteclock 22.1

- It is possible to specify empty project and service when calling `m start`. It is also
  possible to omit the `note` part of an activity, this implies an empty note. See
  [#4](https://github.com/iliakur/miteclock/issues/4).
- Documentation and one error message have been reworked to improve clarity.

## miteclock 2.3

- Fix crash at initialization if config folder does not exist. See issue #3.
- Fix crash of `m status` if entries without project or service name are present.

## miteclock 2.2

- Extended test coverage, found and fixed a bug in `m status` as a result.
- Reworked documentation in README, CHANGELOG and help messages.

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

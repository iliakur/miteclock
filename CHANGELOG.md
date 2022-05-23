# Changelog

Versions follow [CalVer](https://calver.org/) with a strict backwards-compatibility
policy. The **first number** of the version is the short year (last 2 digits). The
**second number** is incremented with each release, starting at 1 for each year.

## miteclock 22.3

- Rename `client` field to `customer` to be more consistent with mite terminology. This
  breaks compatibility, for that I apologize. I hope the damage is minimal, however,
  since the feature is new and has not been adopted yet as far as I know.
- Include customer information in reports and error messages with projects.
- Documentation for advanced pattern definitions.

## miteclock 22.2

- Fix field name for retrieving client/customer name.

## miteclock 22.1

- Support omitting the note part of an activity and leaving project or service empty, as
  described in [#4](https://github.com/iliakur/miteclock/issues/4)
- Support selecting projects based also on client name, as requested in
  [#5](https://github.com/iliakur/miteclock/issues/5).
- Switch to CalVer scheme. This way we follow an established convention that
  communicates clearly.

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

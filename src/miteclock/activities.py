"""This module deals with converting activity descriptions into mite time entries.

An activity description is how we specify an activity on the command line.
It can be a combination of shortcut keys, patterns for selecting projects
and services, notes entered verbatim.

The shortcuts in this combination are expanded recursively while note entries
and raw patterns are passed unchanged.

The only restriction on the possible combinations is that they must result in
a valid time entry specification that mite can understand.

"Valid" means two things:
- there are exactly 3 fields: project pattern, service pattern, note
- project and service patterns match exactly one project and service each
"""
import operator
from dataclasses import dataclass
from functools import singledispatch
from typing import Any, Dict, List, Mapping, Union

MATCHING_PREDICATES = {"strict": operator.eq, "substring": operator.contains}


@dataclass
class Pattern:
    pattern: str
    match: str = "substring"


def find_unique(entries, entry_type, pattern):
    """Tries to find a unique entry that matches the pattern.

    Ensures there is exactly one match for the given pattern.
    """
    if isinstance(pattern, str):
        pattern = Pattern(pattern)
    else:
        pattern = Pattern(**pattern)
    pred = MATCHING_PREDICATES[pattern.match]
    # The order matters here because operator.contains expects the filter pattern
    # to be the second argument!
    matches = [e for e in entries if pred(e["name"], pattern.pattern)]
    # The validation logic is included here and not in the caller function
    # because it is the same for services and projects.
    if not matches:
        raise ValueError(f"'{pattern.pattern}' did not match any {entry_type}.\n")
    if len(matches) > 1:
        raise ValueError(
            f"'{pattern.pattern}' matched the following multiple {entry_type}:\n"
            + "\n".join(m["name"] for m in matches)
            + "\n\n"
            + "Please provide an unambiguous pattern."
        )
    return matches[0]


def to_time_entry_spec(activity, shortcuts, projects, services):
    """Turn an activity into a time entry specification."""
    assert activity
    if len(activity) > 3:
        raise ValueError("Activity definition too long, please enter at most 3 items.")
    values = []
    for a in activity:
        values += _expand(a, shortcuts)
    if len(values) != 3:
        raise ValueError(
            f"Expanding your input resulted in an invalid time entry spec: {values},\n"
            "Please check your input and shortcuts."
        )
    proj_pattern, service_pattern, note = values
    matching_project = find_unique(projects, "projects", proj_pattern)
    matching_service = find_unique(services, "services", service_pattern)
    return {
        "project_id": matching_project["id"],
        "service_id": matching_service["id"],
        "note": note,
    }


def _expand(key, shortcuts, breadcrumbs=None):
    """Given shortcut key and mapping of shortcuts expand the shortcut key.

    Return the key itself if it is not found in the mapping.
    Avoids expansion cycles by keeping track of expansion history in the
    `breadcrumbs` argument to recursive calls.
    """
    breadcrumbs = [] if breadcrumbs is None else breadcrumbs
    if key in breadcrumbs:
        cyclic_path = " -> ".join(breadcrumbs)
        raise ValueError(
            f"Detected a cycle when expanding key '{key}': {cyclic_path}\n"
            "Please check your shortcuts."
        )
    # There are two termination conditions for the recursion:
    # - The key is in fact clearly a pattern (a dictionary for now).
    #   This would definitely exclude it as a candidate for further expansion.
    # - The key is a string (a note, a simple pattern) but is not found in
    #   our shortcut mapping. This simply means it cannot be further expanded.
    if isinstance(key, dict) or key not in shortcuts:
        return [key]
    expansion = shortcuts[key]
    expansions = expansion if isinstance(expansion, list) else [expansion]
    next_level = []
    for sk in expansions:
        next_level += _expand(sk, shortcuts, breadcrumbs=breadcrumbs + [key])
    return next_level


ShortcutData = Dict[str, Union[str, List[str], Dict[str, str]]]


def validate_shortcuts(sc: ShortcutData) -> ShortcutData:
    # TODO: document that extent of validation doesn't include checking for cycles.
    if not isinstance(sc, Mapping):
        raise TypeError(
            f"Shortcut definition must be a dictionary or mapping, got {type(sc)}."
        )
    for k, v in sc.items():
        try:
            _validate_shortcut_expansion(v)
        except (ValueError, TypeError) as e:
            raise e.__class__(f"The expansion for shortcut '{k}' is invalid: {e}")
    return sc


@singledispatch
def _validate_shortcut_expansion(val: Any) -> None:
    raise TypeError(f"Unsupported expansion type: {type(val)}.")


@_validate_shortcut_expansion.register(str)
def _(val: str) -> None:
    pass


@_validate_shortcut_expansion.register(list)
def _(val: List[str]) -> None:
    if not val:
        raise ValueError("List expansion cannot be empty.")
    if len(val) > 3:
        raise ValueError(
            f"Shortcut expansions cannot be longer than 3 items, got {len(val)}."
        )


@_validate_shortcut_expansion.register(dict)
def _(val: Dict[str, Dict[str, str]]) -> None:
    # TODO: Include some validation here
    pass

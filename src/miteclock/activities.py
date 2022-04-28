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
from abc import ABC, abstractmethod
from functools import singledispatch
from typing import Any, Dict, List, Mapping, Union

import attrs
import tomlkit


class MatchingPredicate(ABC):
    @abstractmethod
    def __call__(self, entry) -> bool:
        ...

    @property
    @abstractmethod
    def definition(self) -> str:
        ...


@attrs.define
class StrictMatch(MatchingPredicate):
    fieldname: str
    pattern: str
    definition: str

    def __call__(self, entry):
        return entry[self.fieldname] == self.pattern


@attrs.define
class SubstringMatch(MatchingPredicate):
    fieldname: str
    pattern: str
    definition: str

    def __call__(self, entry):
        return self.pattern in entry[self.fieldname]


def _parse_matcher(pattern_data):
    if isinstance(pattern_data, str):
        return SubstringMatch("name", pattern_data, pattern_data)
    definition = tomlkit.dumps(pattern_data)
    if pattern_data.get("match", "substring") == "substring":
        return SubstringMatch("name", pattern_data["pattern"], definition)
    return StrictMatch("name", pattern_data["pattern"], definition)


def find_unique(entries, entry_type, pattern_data):
    """Tries to find a unique entry that matches the pattern.

    Ensures there is exactly one match for the given pattern.
    """
    pred = _parse_matcher(pattern_data)
    matches = [e for e in entries if pred(e)]
    if not matches:
        raise ValueError(f"'{pred.definition}' did not match any {entry_type}.\n")
    if len(matches) > 1:
        raise ValueError(
            f"'{pred.definition}' matched the following multiple {entry_type}:\n"
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
    for key in activity:
        values += _expand(key, shortcuts)
    if len(values) == 2:
        values += [""]
    if len(values) != 3:
        raise ValueError(
            f"Cannot interpret the result of expanding your input: {values},\n"
            "The result should have the following items (order matters!): "
            "project, service, note (optional)."
        )
    proj_pattern, service_pattern, note = values
    matching_project = (
        None
        if proj_pattern == ""
        else find_unique(projects, "projects", proj_pattern)["id"]
    )
    matching_service = (
        None
        if service_pattern == ""
        else find_unique(services, "services", service_pattern)["id"]
    )
    return {
        "project_id": matching_project,
        "service_id": matching_service,
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

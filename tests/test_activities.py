import pytest

from miteclock import activities


@pytest.mark.parametrize(
    "activity, time_entry",
    [
        (["daily"], {"note": "daily stand-up", "service_id": 6, "project_id": 1}),
        (["weekly"], {"note": "weekly meeting", "service_id": 6, "project_id": 1}),
        (
            ["a", "d", "hunting for bugs"],
            {"note": "hunting for bugs", "service_id": 0, "project_id": 3},
        ),
        (
            ["o", "q", "reviewing a merge request"],
            {"note": "reviewing a merge request", "service_id": 4, "project_id": 1},
        ),
        (["nested"], {"note": "hunting for bugs", "service_id": 0, "project_id": 3}),
    ],
)
def test_to_time_entry_spec(activity, shortcuts, time_entry, projects, services):
    assert (
        activities.to_time_entry_spec(activity, shortcuts, projects, services)
        == time_entry
    )


@pytest.mark.parametrize(
    "activity",
    [
        # Single item that has no shortcut expansion associated with it.
        ["b"],
        # Input that is longer than 3 items should not work either.
        ["a", "b", "c", "d"],
    ],
)
def test_to_time_entry_spec_invalid_input(activity):
    with pytest.raises(ValueError):
        # Neither projects, nor services matter here.
        # Shortcuts are left empty to make sure nothing is expanded.
        activities.to_time_entry_spec(activity, {}, [], [])


def test_to_time_entry_spec_empty_input():
    """An empty input should never happen."""
    with pytest.raises(AssertionError):
        activities.to_time_entry_spec([], {}, [], [])


def test_to_time_entry_spec_avoids_cycles():
    with pytest.raises(ValueError) as e:
        activities.to_time_entry_spec(["a"], {"a": "b", "b": "a"}, [], [])
        assert "a -> b -> a" in e


@pytest.mark.parametrize(
    "pattern, match",
    [
        # This matches full entry name even though it's checking containment.
        ("Development", {"name": "Development", "id": 0}),
        # This needs to be strict to match only one service.
        ({"pattern": "QA", "match": "strict"}, {"name": "QA", "id": 4}),
        # These two match the unique part of a service name.
        ("Language", {"name": "Language QA", "id": 5}),
        ("Comm", {"name": "Communication", "id": 6}),
    ],
)
def test_find_unique(pattern, match, services):
    assert activities.find_unique(services, "services", pattern) == match


@pytest.mark.parametrize(
    "pattern",
    [
        # These selectors are ambiguous, will match multiple services.
        "Dev",
        "QA",
        # This will not match any services.
        "dev",
        # This is too strict, will not match any entries exactly.
        {"pattern": "Language", "match": "strict"},
    ],
)
def test_find_unique_invalid(services, pattern):
    with pytest.raises(ValueError):
        activities.find_unique(services, "services", pattern)

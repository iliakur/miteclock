import hypothesis.strategies as st
import pytest
from hypothesis import given

from miteclock import activities as a


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
    assert a.to_time_entry_spec(activity, shortcuts, projects, services) == time_entry


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
        a.to_time_entry_spec(activity, {}, [], [])


def test_to_time_entry_spec_empty_input():
    """An empty input should never happen."""
    with pytest.raises(AssertionError):
        a.to_time_entry_spec([], {}, [], [])


def test_to_time_entry_spec_avoids_cycles():
    with pytest.raises(ValueError) as excinfo:
        a.to_time_entry_spec(["a"], {"a": "b", "b": "a"}, [], [])
        assert "a -> b -> a" in str(excinfo.value)


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
    assert a.find_unique(services, "services", pattern) == match


@pytest.mark.parametrize(
    "pattern, error_msg",
    [
        # This selector is ambiguous, will match multiple services.
        (
            "Dev",
            (
                "'Dev' matched the following multiple services:\n"
                "Development\n"
                "Developer Training\n"
                "DevOps\n\n"
                "Please provide an unambiguous pattern."
            ),
        ),
        # This will not match any services.
        ("dev", "'dev' did not match any services.\n"),
        # This is too strict, will not match any entries exactly.
        (
            {"pattern": "Language", "match": "strict"},
            '\'{pattern = "Language", match = "strict"}\' '
            "did not match any services.\n",
        ),
    ],
)
def test_find_unique_invalid(services, pattern, error_msg):
    with pytest.raises(ValueError) as excinfo:
        a.find_unique(services, "services", pattern)
    assert str(excinfo.value) == error_msg


def test_find_unique_ambiguous_project(projects):
    with pytest.raises(ValueError) as excinfo:
        a.find_unique(projects, "projects", "AT&T")
    assert str(excinfo.value) == (
        "'AT&T' matched the following multiple projects:\n"
        "AT&T/Designing OS\n"
        "AT&T/Designing OS (Customer: AT&T)\n\n"
        "Please provide an unambiguous pattern."
    )


numbers = st.integers() | st.floats()


@given(st.lists(numbers | st.text()) | numbers | st.text())
def test_validate_shortcuts_not_dict(data):
    with pytest.raises(TypeError):
        a.validate_shortcuts(data)


@given(
    st.dictionaries(st.text(), st.lists(st.text(), min_size=1, max_size=3) | st.text())
)
def test_validate_shortcuts_valid_simple_patterns(data):
    a.validate_shortcuts(data)


@given(
    st.dictionaries(
        st.text(),
        st.lists(st.text(), min_size=4) | st.just([]) | numbers,
        min_size=1,  # Empty dictionary is valid, so insist here on at least one key.
    )
)
def test_validate_shortcuts_invalid_simple_patterns(data):
    with pytest.raises((TypeError, ValueError)):
        a.validate_shortcuts(data)


def test_empty_activity_spec():
    assert a.to_time_entry_spec(["", "", ""], {}, [], []) == {
        "project_id": None,
        "service_id": None,
        "note": "",
    }


def test_activity_has_no_note():
    assert a.to_time_entry_spec(["", ""], {}, [], []) == {
        "project_id": None,
        "service_id": None,
        "note": "",
    }


@pytest.mark.parametrize(
    "pattern_data, match",
    [
        (
            {"project": "Backend", "customer": {"pattern": "ZDF", "match": "strict"}},
            {"name": "Rewriting Backend", "customer_name": "ZDF", "id": 2},
        ),
        (
            {"project": "Backend", "customer": "ARD"},
            {"name": "Rewriting Backend", "customer_name": "ARD", "id": 5},
        ),
    ],
)
def test_match_client_and_project(pattern_data, match):
    projects = [
        {"name": "Company_Internal_2020", "customer_name": None, "id": 0},
        {"name": "OCP ED-209", "customer_name": None, "id": 1},
        {"name": "Rewriting Backend", "customer_name": "ZDF", "id": 2},
        {"name": "Rewriting Backend", "customer_name": "ARD", "id": 5},
        {"name": "ACME :: Squashing Bugs", "customer_name": None, "id": 3},
        {"name": "AT&T/Designing OS", "customer_name": None, "id": 4},
    ]
    assert a.find_unique(projects, "projects", pattern_data) == match


@pytest.mark.parametrize(
    "data, pattern",
    [
        pytest.param(
            "test",
            a.Pattern(a.SubstringMatch("name", "test"), "test"),
            id="Implicit substring match definition.",
        ),
        pytest.param(
            {"pattern": "test", "match": "substring"},
            a.Pattern(
                a.SubstringMatch("name", "test"),
                '{pattern = "test", match = "substring"}',
            ),
            id="Explicitly say match is substring.",
        ),
        pytest.param(
            {"pattern": "test", "match": "strict"},
            a.Pattern(
                a.StrictMatch("name", "test"),
                '{pattern = "test", match = "strict"}',
            ),
            id="Explicitly say match is strict.",
        ),
    ],
)
def test_parse_valid_patterns(data, pattern):
    assert a.Pattern.parse(data) == pattern


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"client": "AB"}, id="Only client key present."),
        pytest.param({"project": {"project": "test"}}, id="Nested project key."),
        pytest.param({"match": "strict"}, id="Pattern key is missing."),
    ],
)
def test_parse_invalid_patterns(data):
    with pytest.raises(ValueError):
        a.Pattern.parse(data)


def test_parse_equivalent_project_pattern():
    """Matching logic for equivalent pattern definitions should be the same.

    The definition part should preserve the difference.
    """
    p1 = a.Pattern.parse({"pattern": "test", "match": "strict"})
    p2 = a.Pattern.parse({"project": {"pattern": "test", "match": "strict"}})

    assert p1.matches == p2.matches
    assert p1.definition != p2.definition

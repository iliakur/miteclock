"""This module knows all things mite-related."""
from dataclasses import dataclass

import backoff
import requests


def init_api(base_url, apikey, app_name, app_version):
    """Set up session for making requests to mite api."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": f"{app_name}: v{app_version}",
            "Content-Type": "application/json",
            "X-MiteApiKey": apikey,
        }
    )
    # Adding a hook to always make sure our requests succeed.
    # Kudos: https://stackoverflow.com/a/45470227/4501212
    session.hooks = {"response": [lambda r, *args, **kwargs: r.raise_for_status()]}

    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.Timeout, requests.exceptions.ConnectionError),
        max_time=60,
    )
    def api(method, resource_path, **requests_kwargs):
        """Make request to mite api using HTTP method, resource path and kwargs.

        Checks response for errors (will raise) and returns its json payload.
        """
        return session.request(
            method,
            f"{base_url}/{resource_path}.json",
            timeout=10,
            **requests_kwargs,
        ).json()

    return api


@dataclass
class TrackedTimeEntry:
    """Time entry for which the clock is currently running."""

    id: int

    @classmethod
    def from_response(cls, resp_data):
        return cls(resp_data["id"])


class StopWatch:
    """Adapter for interacting with Mite's stopwatch conveniently."""

    def __init__(self, requester):
        self._requester = requester

    def tracking_time_entry(self):
        """Check if stopwatch is running for an entry.

        If yes, return that entry's ID.
        If no, return None.
        """
        tracker = self._requester("get", "tracker")["tracker"]
        if not tracker:
            return None
        return TrackedTimeEntry.from_response(tracker["tracking_time_entry"])

    def stop(self, entry_id):
        """Stop the clock for entry given its ID."""
        return self._requester("delete", f"tracker/{entry_id}")

    def start(self, entry_id):
        """Start counting time for an entry specified by its ID."""
        return self._requester("patch", f"tracker/{entry_id}")

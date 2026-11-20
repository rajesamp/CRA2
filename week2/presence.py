"""Ephemeral, masked recent activity; this is not a Google login directory."""
from html import escape
import threading
import time

from week2.iap import Principal


class Presence:
    def __init__(self, *, clock=time.monotonic, ttl=300, capacity=1001):
        self.clock, self.ttl, self.capacity = clock, ttl, capacity
        self.users = {}
        self.lock = threading.Lock()

    def touch(self, principal):
        if not isinstance(principal, Principal):
            raise ValueError("Verified identity unavailable")
        with self.lock:
            now = self.clock()
            self.users = {key: row for key, row in self.users.items() if now - row[1] < self.ttl}
            if principal.key in self.users or len(self.users) < self.capacity:
                self.users[principal.key] = (principal.masked_email, now)

    def view(self, principal):
        self.touch(principal)
        with self.lock:
            users = sorted((row[0], key == principal.key) for key, row in self.users.items())
        rows = "".join('<li><span class="cra-status-dot" aria-hidden="true"></span>'
                       + escape(email) + (' <span class="cra-you">you</span>' if own else '')
                       + '</li>' for email, own in users)
        detail = "Visible to signed-in visitors · active in the last 5 minutes on this app instance."
        return '<section class="cra-presence"><h2>Logged in users</h2><ul>' + rows + '</ul><p>' + detail + '</p></section>'


def principal_from_request(request):
    native = getattr(request, "request", None)
    principal = getattr(getattr(native, "state", None), "cra2_principal", None)
    if not isinstance(principal, Principal) or getattr(request, "username", None) != principal.key:
        raise ValueError("Verified identity unavailable")
    return principal

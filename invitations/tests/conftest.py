from dataclasses import dataclass

import pytest

from invitations.identity import OWNER
from invitations.service import Pilot


@dataclass
class Clock:
    now: float = 1_800_000_000

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def pilot(tmp_path, clock):
    app = Pilot(tmp_path / "private", OWNER, clock=clock)
    app.hold(OWNER, False)
    return app

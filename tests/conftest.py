from collections.abc import Iterator

import pytest

from tests.harness import Harness, build_harness


@pytest.fixture
def harness() -> Iterator[Harness]:
    harness, stack = build_harness()
    with stack:
        # Les sockets d'abord, le client ensuite : ordre inverse de l'ouverture.
        with harness.stack:
            yield harness

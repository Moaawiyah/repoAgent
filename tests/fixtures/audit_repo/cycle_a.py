"""Half of a fixture circular import (module-level, statically detectable)."""

from cycle_b import helper_b


def helper_a():
    return helper_b()

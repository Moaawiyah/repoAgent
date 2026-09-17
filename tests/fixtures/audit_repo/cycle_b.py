"""Other half of a fixture circular import."""

from cycle_a import helper_a


def helper_b():
    return 1


def calls_a():
    return helper_a()

"""Sixteen distinct callers of `hub.process` to exercise fan-in coupling."""

import hub


def caller_1():
    return hub.process(1)


def caller_2():
    return hub.process(2)


def caller_3():
    return hub.process(3)


def caller_4():
    return hub.process(4)


def caller_5():
    return hub.process(5)


def caller_6():
    return hub.process(6)


def caller_7():
    return hub.process(7)


def caller_8():
    return hub.process(8)


def caller_9():
    return hub.process(9)


def caller_10():
    return hub.process(10)


def caller_11():
    return hub.process(11)


def caller_12():
    return hub.process(12)


def caller_13():
    return hub.process(13)


def caller_14():
    return hub.process(14)


def caller_15():
    return hub.process(15)


def caller_16():
    return hub.process(16)

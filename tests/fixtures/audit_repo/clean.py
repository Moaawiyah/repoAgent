"""Fixture module with none of the audit smells (false-positive coverage)."""


def append_item(item, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket


def read_all(path):
    with open(path) as handle:
        return handle.read()


def run_command(command):
    import subprocess

    subprocess.run(command, shell=False)


def greet(name=None):
    if name is None:
        return "hello"
    return name.upper()


def normalize(value):
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"Cannot normalize {value!r}") from error

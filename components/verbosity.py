
VERBOSITY = 0


def v_print(v: int, *args):
    if VERBOSITY >= v:
        print(*args)
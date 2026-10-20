"""Group -> flag contract and flag-combination helpers shared by the transport flag tests (F4000302)."""

from itertools import combinations

import config

FLAG_OF = {'code': 'CODE_ENABLED', 'task': 'TASK_ENABLED', 'build': 'BUILD_ENABLED'}


def combinations_of(groups):
    """All subsets of `groups` as frozensets, smallest first (the group names that are disabled)."""
    ordered = sorted(groups)
    return [frozenset(c) for size in range(len(ordered) + 1) for c in combinations(ordered, size)]


def ids(disabled):
    return '+'.join(sorted(disabled)) or 'none'


def set_flags(monkeypatch, disabled, groups=None):
    for group in groups or FLAG_OF:
        monkeypatch.setattr(config, FLAG_OF[group], group not in disabled)

"""Compare destination order and occurrence counts, allowing Plex duplicate collapse."""
from collections import Counter


def compare(expected, items):
    expected = [str(value) for value in expected]
    actual = [str(item.get('plex_id')) for item in items]
    # A server may collapse repeats. Accept only a subsequence with all distinct IDs,
    # no extra occurrences, and at least one retained occurrence of every expected ID.
    remaining = iter(expected)
    ordered = all(any(candidate == value for candidate in remaining) for value in actual)
    collapsed = actual != expected and set(actual) == set(expected) and ordered and not (Counter(actual)-Counter(expected))
    missing, extra = Counter(expected)-Counter(actual), Counter(actual)-Counter(expected)
    return {'ok': actual == expected or collapsed, 'duplicates_collapsed': sum(missing.values()) if collapsed else 0,
            'missing': dict(missing), 'extra': dict(extra), 'order_matches': ordered,
            'expected_count': len(expected), 'actual_count': len(actual)}


def describe(result):
    return (f"Plex verification: expected {result['expected_count']} occurrences, retained {result['actual_count']}; "
            f"missing IDs/counts: {result['missing']}; extra IDs/counts: {result['extra']}; source order preserved: {result['order_matches']}")

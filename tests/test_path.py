import pytest
from deepdiff import DeepDiff
from deepdiff.path import _path_to_elements, GET, GETATTR, extract, parse_path, stringify_path, stringify_element, _add_to_elements


@pytest.mark.parametrize('test_num, path, expected', [
    (1, "root[4]['b'][3]", [(4, GET), ('b', GET), (3, GET)]),
    (2, "root[4].b[3]", [(4, GET), ('b', GETATTR), (3, GET)]),
    (3, "root[4].b['a3']", [(4, GET), ('b', GETATTR), ('a3', GET)]),
    (4, "root[4.3].b['a3']", [(4.3, GET), ('b', GETATTR), ('a3', GET)]),
    (5, "root.a.b", [('a', GETATTR), ('b', GETATTR)]),
    (6, "root.hello", [('hello', GETATTR)]),
    (7, "root['h']", [('h', GET)]),
    (8, "root['a\rb']", [('a\rb', GET)]),
    (9, "root['a\\rb']", [('a\\rb', GET)]),
    (10, "root", []),
    (11, ((4, GET), ('b', GET)), ((4, GET), ('b', GET))),
])
def test_path_to_elements(test_num, path, expected):
    result = _path_to_elements(path, root_element=None)
    assert tuple(expected) == result, f"test_path_to_elements #{test_num} failed"
    if isinstance(path, str):
        path_again = stringify_path(path=result)
        assert path == path_again, f"test_path_to_elements #{test_num} failed"


@pytest.mark.parametrize('obj, path, expected', [
    ({1: [2, 3], 2: [4, 5]},
     "root[2][1]",
     5),
    ({1: [{'2': 'b'}, 3], 2: {4, 5}},
     "root[1][0]['2']",
     'b'
     ),
    ({'test [a]': 'b'},
     "root['test [a]']",
     'b'
     ),
    ({"a']['b']['c": 1},
     """root["a']['b']['c"]""",
     1
     ),
])
def test_get_item(obj, path, expected):
    result = extract(obj, path)
    assert expected == result


def test_parse_path():
    result = parse_path("root[1][2]['age']")
    assert [1, 2, 'age'] == result
    result2 = parse_path("root[1][2]['age']", include_actions=True)
    assert [{'element': 1, 'action': 'GET'}, {'element': 2, 'action': 'GET'}, {'element': 'age', 'action': 'GET'}] == result2
    result3 = parse_path("root['joe'].age")
    assert ['joe', 'age'] == result3
    result4 = parse_path("root['joe'].age", include_actions=True)
    assert [{'element': 'joe', 'action': 'GET'}, {'element': 'age', 'action': 'GETATTR'}] == result4


@pytest.mark.parametrize('test_num, elem, inside, expected', [
    (
        1,
        "'hello'",
        None,
        [('hello', GET)],
    ),
    (
        2,
        "'a\rb'",
        None,
        [('a\rb', GET)],
    ),
])
def test__add_to_elements(test_num, elem, inside, expected):
    elements = []
    _add_to_elements(elements, elem, inside)
    assert expected == elements


# Keys covering the quote-form matrix: no quote, single quote only,
# double quote only, and both quotes mixed in various positions.
QUOTE_MATRIX_KEYS = [
    ('plain', "'plain'"),
    ("it's", "\"it's\""),
    ("'leading", "\"'leading\""),
    ("trailing'", "\"trailing'\""),
    ('say "hi"', "'say \"hi\"'"),
    ('"leading', "'\"leading'"),
    ('trailing"', "'trailing\"'"),
    ('a\'"b', '"a𝆺𝅥𝅯\'𝆺𝅥𝅯"b"'),
    ('"a\'b', '"𝆺𝅥𝅯"a𝆺𝅥𝅯\'b"'),
    ('\'"', '"𝆺𝅥𝅯\'𝆺𝅥𝅯""'),
    ('a\'"', '"a𝆺𝅥𝅯\'𝆺𝅥𝅯""'),
    ('\'"a', '"𝆺𝅥𝅯\'𝆺𝅥𝅯"a"'),
]


@pytest.mark.parametrize('key, expected', QUOTE_MATRIX_KEYS)
def test_stringify_element_quote_matrix(key, expected):
    """The serialized form of each quote shape must stay byte-exact."""
    result = stringify_element(key, quote_str="'{}'")
    assert expected == result


@pytest.mark.parametrize('key, expected', QUOTE_MATRIX_KEYS)
def test_stringify_element_round_trip(key, expected):
    """Every serialized form must parse back to the original key."""
    path = f"root[{expected}]"
    elements = _path_to_elements(path, root_element=None)
    assert [(key, GET)] == list(elements)
    assert key == parse_path(path)[0]


@pytest.mark.parametrize('key, expected', QUOTE_MATRIX_KEYS)
def test_extract_replay_quote_matrix(key, expected):
    """Paths persisted in a diff report must replay against the source object."""
    obj = {'nested': [0, {key: 'value'}]}
    path = f"root['nested'][1][{expected}]"
    assert 'value' == extract(obj, path)


@pytest.mark.parametrize('key, expected', QUOTE_MATRIX_KEYS)
def test_diff_paths_replay_both_views(key, expected):
    """Text view and tree view paths for quote-laden keys must both replay."""
    t1 = {'outer': [{'inner': {key: 1}}]}
    t2 = {'outer': [{'inner': {key: 2}}]}

    text_diff = DeepDiff(t1, t2)
    text_paths = list(text_diff['values_changed'])
    assert [f"root['outer'][0]['inner'][{expected}]"] == text_paths
    for path in text_paths:
        assert 2 == extract(t2, path)

    tree_diff = DeepDiff(t1, t2, view='tree')
    tree_paths = [item.path() for item in tree_diff['values_changed']]
    assert text_paths == tree_paths
    for path in tree_paths:
        assert 2 == extract(t2, path)


def test_diff_paths_replay_nested_mixed_keys():
    """Nested structures with mixed-quote keys at several levels must replay."""
    key1 = '''a'"b'''
    key2 = '''"x'y'''
    t1 = {key1: {key2: [{'''c'"''': 1}]}}
    t2 = {key1: {key2: [{'''c'"''': 2}]}}
    for view in ('text', 'tree'):
        diff = DeepDiff(t1, t2, view=view)
        if view == 'text':
            paths = list(diff['values_changed'])
        else:
            paths = [item.path() for item in diff['values_changed']]
        assert 1 == len(paths)
        assert 2 == extract(t2, paths[0])
        assert 1 == extract(t1, paths[0])

import pytest

from ipybox.mcp.utils import ReplaceResult, _replace_variables, replace_variables


@pytest.mark.parametrize(
    "template,variables,expected_rendered,expected_replaced,expected_missing,expected_total",
    [
        # Basic replacement
        (
            "Hello {NAME}, welcome to {PLACE}!",
            {"NAME": "Alice", "PLACE": "Wonderland"},
            "Hello Alice, welcome to Wonderland!",
            {"NAME", "PLACE"},
            set(),
            2,
        ),
        # Missing variables
        (
            "Hello {NAME}, welcome to {PLACE}!",
            {"NAME": "Alice"},
            "Hello Alice, welcome to {PLACE}!",
            {"NAME"},
            {"PLACE"},
            2,
        ),
        # No variables in template
        ("Hello World!", {"NAME": "Alice"}, "Hello World!", set(), set(), 0),
        # Empty template
        ("", {"NAME": "Alice"}, "", set(), set(), 0),
        # Empty variables dict
        ("Hello {NAME}!", {}, "Hello {NAME}!", set(), {"NAME"}, 1),
        # Duplicate variables in template
        (
            "Hello {NAME}, how are you {NAME}?",
            {"NAME": "Alice"},
            "Hello Alice, how are you Alice?",
            {"NAME"},
            set(),
            1,
        ),
        # Underscore in variable name
        ("Value: {VAR_NAME}", {"VAR_NAME": "test_value"}, "Value: test_value", {"VAR_NAME"}, set(), 1),
        # Invalid variable patterns ignored (VAR-NAME with hyphen and empty braces)
        (
            "Invalid {123} and {VAR-NAME} and {} but valid {VALID}",
            {"VALID": "good", "123": "bad", "VAR-NAME": "bad"},
            "Invalid bad and {VAR-NAME} and {} but valid good",
            {"VALID", "123"},
            set(),
            2,
        ),
        # Case sensitive variables
        (
            "Hello {name} and {NAME}",
            {"name": "alice", "NAME": "ALICE"},
            "Hello alice and ALICE",
            {"name", "NAME"},
            set(),
            2,
        ),
        # Special characters in values
        (
            "Message: {MSG}",
            {"MSG": "Hello $world {test} [brackets]"},
            "Message: Hello $world {test} [brackets]",
            {"MSG"},
            set(),
            1,
        ),
    ],
)
def test_replace_variables(template, variables, expected_rendered, expected_replaced, expected_missing, expected_total):
    result = _replace_variables(template, variables)

    assert result.replaced == expected_rendered
    assert result.replaced_variables == expected_replaced
    assert result.missing_variables == expected_missing
    assert result.total_variables == expected_total


@pytest.mark.parametrize(
    "rendered,replaced_variables,missing_variables,expected_total",
    [
        # Mixed variables
        ("test", {"A", "B"}, {"C"}, 3),
        # Empty variables lists
        ("test", set(), set(), 0),
        # Only replaced variables
        ("test", {"A", "B", "C"}, set(), 3),
        # Only missing variables
        ("test", set(), {"X", "Y"}, 2),
    ],
)
def test_replace_result_total_variables(rendered, replaced_variables, missing_variables, expected_total):
    result = ReplaceResult(
        replaced=rendered, replaced_variables=replaced_variables, missing_variables=missing_variables
    )

    assert result.total_variables == expected_total


@pytest.mark.parametrize(
    "template,variables,expected_rendered,expected_replaced,expected_missing",
    [
        # Simple dict with string values
        (
            {"message": "Hello {NAME}", "greeting": "Welcome to {PLACE}!"},
            {"NAME": "Alice", "PLACE": "Wonderland"},
            {"message": "Hello Alice", "greeting": "Welcome to Wonderland!"},
            {"NAME", "PLACE"},
            set(),
        ),
        # Nested dict
        (
            {
                "user": {"name": "{USER_NAME}", "role": "{USER_ROLE}"},
                "config": {"timeout": 30, "message": "User {USER_NAME} logged in"},
            },
            {"USER_NAME": "Bob", "USER_ROLE": "admin"},
            {
                "user": {"name": "Bob", "role": "admin"},
                "config": {"timeout": 30, "message": "User Bob logged in"},
            },
            {"USER_NAME", "USER_ROLE"},
            set(),
        ),
        # Dict with list values
        (
            {
                "items": ["Item {ITEM1}", "Item {ITEM2}", "Item {ITEM3}"],
                "title": "List of {COUNT} items",
            },
            {"ITEM1": "Apple", "ITEM2": "Banana", "COUNT": "3"},
            {
                "items": ["Item Apple", "Item Banana", "Item {ITEM3}"],
                "title": "List of 3 items",
            },
            {"ITEM1", "ITEM2", "COUNT"},
            {"ITEM3"},
        ),
        # Mixed nested structures
        (
            {
                "metadata": {
                    "author": "{AUTHOR}",
                    "tags": ["{TAG1}", "{TAG2}", "static-tag"],
                    "nested": {"deep": {"value": "Deep {VALUE}"}},
                },
                "count": 42,
                "enabled": True,
            },
            {"AUTHOR": "Jane", "TAG1": "python", "VALUE": "secret"},
            {
                "metadata": {
                    "author": "Jane",
                    "tags": ["python", "{TAG2}", "static-tag"],
                    "nested": {"deep": {"value": "Deep secret"}},
                },
                "count": 42,
                "enabled": True,
            },
            {"AUTHOR", "TAG1", "VALUE"},
            {"TAG2"},
        ),
        # Empty dict
        ({}, {"NAME": "Alice"}, {}, set(), set()),
        # Dict with no variables
        (
            {"message": "Hello World", "count": 5},
            {"NAME": "Alice"},
            {"message": "Hello World", "count": 5},
            set(),
            set(),
        ),
        # Dict with missing variables only
        (
            {"error": "User {USER} not found in {LOCATION}"},
            {},
            {"error": "User {USER} not found in {LOCATION}"},
            set(),
            {"USER", "LOCATION"},
        ),
        # Dict with duplicate variables across different values
        (
            {
                "greeting": "Hello {NAME}",
                "farewell": "Goodbye {NAME}",
                "nested": {"msg": "See you later {NAME}"},
            },
            {"NAME": "Charlie"},
            {
                "greeting": "Hello Charlie",
                "farewell": "Goodbye Charlie",
                "nested": {"msg": "See you later Charlie"},
            },
            {"NAME"},
            set(),
        ),
        # Dict with non-string values preserved
        (
            {
                "text": "Value is {VALUE}",
                "number": 123,
                "float": 45.67,
                "boolean": False,
                "null": None,
                "list": [1, 2, "{NUM}", 3],
            },
            {"VALUE": "test", "NUM": "2.5"},
            {
                "text": "Value is test",
                "number": 123,
                "float": 45.67,
                "boolean": False,
                "null": None,
                "list": [1, 2, "2.5", 3],
            },
            {"VALUE", "NUM"},
            set(),
        ),
    ],
)
def test_replace_variables_dict(template, variables, expected_rendered, expected_replaced, expected_missing):
    result = replace_variables(template, variables)

    assert result.replaced == expected_rendered
    assert result.replaced_variables == expected_replaced
    assert result.missing_variables == expected_missing
    assert result.total_variables == len(expected_replaced) + len(expected_missing)

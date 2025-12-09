from ipybox.vars import replace_variables


class TestReplaceVariables:
    """Tests for replace_variables function."""

    def test_basic_replacement(self):
        template = {"env": {"KEY": "${VAR}"}}
        variables = {"VAR": "value"}

        result = replace_variables(template, variables)

        assert result.replaced == {"env": {"KEY": "value"}}
        assert result.replaced_variables == {"VAR"}
        assert result.missing_variables == set()

    def test_mcp_env_params(self):
        template = {
            "command": "npx",
            "args": ["-y", "@brave/brave-search-mcp-server"],
            "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        }
        variables = {"BRAVE_API_KEY": "secret123"}

        result = replace_variables(template, variables)

        assert result.replaced["env"]["BRAVE_API_KEY"] == "secret123"
        assert result.replaced["command"] == "npx"
        assert result.replaced["args"] == ["-y", "@brave/brave-search-mcp-server"]
        assert result.replaced_variables == {"BRAVE_API_KEY"}
        assert result.missing_variables == set()

    def test_mcp_headers_params(self):
        template = {
            "url": "https://api.github.com/mcp/",
            "headers": {"Authorization": "Bearer ${GITHUB_API_KEY}"},
        }
        variables = {"GITHUB_API_KEY": "ghp_token123"}

        result = replace_variables(template, variables)

        assert result.replaced["headers"]["Authorization"] == "Bearer ghp_token123"
        assert result.replaced["url"] == "https://api.github.com/mcp/"
        assert result.replaced_variables == {"GITHUB_API_KEY"}

    def test_missing_variable_preserved(self):
        template = {"env": {"KEY": "${MISSING_VAR}"}}
        variables = {}  # type: ignore

        result = replace_variables(template, variables)

        assert result.replaced == {"env": {"KEY": "${MISSING_VAR}"}}
        assert result.replaced_variables == set()
        assert result.missing_variables == {"MISSING_VAR"}

    def test_mixed_replaced_and_missing(self):
        template = {
            "env": {
                "API_KEY": "${API_KEY}",
                "SECRET": "${SECRET}",
            }
        }
        variables = {"API_KEY": "provided_key"}

        result = replace_variables(template, variables)

        assert result.replaced["env"]["API_KEY"] == "provided_key"
        assert result.replaced["env"]["SECRET"] == "${SECRET}"
        assert result.replaced_variables == {"API_KEY"}
        assert result.missing_variables == {"SECRET"}

    def test_nested_dicts(self):
        template = {"a": {"b": {"c": {"d": "${VAR}"}}}}
        variables = {"VAR": "deep_value"}

        result = replace_variables(template, variables)

        assert result.replaced == {"a": {"b": {"c": {"d": "deep_value"}}}}
        assert result.replaced_variables == {"VAR"}

    def test_list_of_strings(self):
        template = {"args": ["-y", "${PKG}", "--option", "${OPT}"]}
        variables = {"PKG": "my-package", "OPT": "value"}

        result = replace_variables(template, variables)

        assert result.replaced["args"] == ["-y", "my-package", "--option", "value"]
        assert result.replaced_variables == {"PKG", "OPT"}

    def test_list_of_dicts(self):
        template = {
            "servers": [
                {"name": "server1", "token": "${TOKEN1}"},
                {"name": "server2", "token": "${TOKEN2}"},
            ]
        }
        variables = {"TOKEN1": "t1", "TOKEN2": "t2"}

        result = replace_variables(template, variables)

        assert result.replaced["servers"][0]["token"] == "t1"
        assert result.replaced["servers"][1]["token"] == "t2"
        assert result.replaced_variables == {"TOKEN1", "TOKEN2"}

    def test_non_string_passthrough(self):
        template = {
            "port": 8080,
            "enabled": True,
            "disabled": False,
            "data": None,
            "ratio": 3.14,
        }
        variables = {}  # type: ignore

        result = replace_variables(template, variables)

        assert result.replaced == template
        assert result.replaced_variables == set()
        assert result.missing_variables == set()

    def test_multiple_variables_in_one_string(self):
        template = {"auth": "Bearer ${TOKEN} for user ${USER}"}
        variables = {"TOKEN": "abc123", "USER": "john"}

        result = replace_variables(template, variables)

        assert result.replaced["auth"] == "Bearer abc123 for user john"
        assert result.replaced_variables == {"TOKEN", "USER"}

    def test_empty_dict(self):
        result = replace_variables({}, {"VAR": "value"})

        assert result.replaced == {}
        assert result.replaced_variables == set()
        assert result.missing_variables == set()

    def test_no_variables_passthrough(self):
        template = {
            "command": "python",
            "args": ["-m", "mymodule"],
            "env": {"PATH": "/usr/bin"},
        }
        variables = {"UNUSED": "value"}

        result = replace_variables(template, variables)

        assert result.replaced == template
        assert result.replaced_variables == set()
        assert result.missing_variables == set()

    def test_total_variables_property(self):
        template = {"a": "${VAR1}", "b": "${VAR2}", "c": "${VAR3}"}
        variables = {"VAR1": "v1", "VAR2": "v2"}

        result = replace_variables(template, variables)

        assert result.total_variables == 3
        assert len(result.replaced_variables) == 2
        assert len(result.missing_variables) == 1

    def test_empty_string_value(self):
        template = {"key": ""}
        variables = {"VAR": "value"}

        result = replace_variables(template, variables)

        assert result.replaced == {"key": ""}
        assert result.replaced_variables == set()

    def test_special_chars_not_matched(self):
        # Patterns with special chars don't match: ${foo-bar} has hyphen
        template = {"key": "${foo-bar}", "other": "${valid}"}
        variables = {"foo-bar": "should_not_match", "valid": "matched"}

        result = replace_variables(template, variables)

        assert result.replaced["key"] == "${foo-bar}"  # Not replaced (hyphen not in pattern)
        assert result.replaced["other"] == "matched"
        assert result.replaced_variables == {"valid"}
        assert result.missing_variables == set()

    def test_same_variable_multiple_occurrences(self):
        template = {
            "first": "${VAR}",
            "second": "${VAR}",
            "nested": {"third": "${VAR}"},
        }
        variables = {"VAR": "value"}

        result = replace_variables(template, variables)

        assert result.replaced["first"] == "value"
        assert result.replaced["second"] == "value"
        assert result.replaced["nested"]["third"] == "value"
        # Variable should only appear once in the set
        assert result.replaced_variables == {"VAR"}

    def test_mixed_content_list(self):
        template = {"items": ["${VAR}", 123, True, None, {"nested": "${VAR2}"}]}
        variables = {"VAR": "str_val", "VAR2": "nested_val"}

        result = replace_variables(template, variables)

        assert result.replaced["items"] == [
            "str_val",
            123,
            True,
            None,
            {"nested": "nested_val"},
        ]
        assert result.replaced_variables == {"VAR", "VAR2"}

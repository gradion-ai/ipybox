import ast

from ipybox.mcp_apigen import (
    generate_function_definition,
    generate_init_definition,
    sanitize_name,
)


def _assert_valid_python(code: str) -> ast.Module:
    """Parse code and return the AST, failing if code is not valid Python."""
    return ast.parse(code)


def _count_import_nodes(tree: ast.Module) -> int:
    """Count Import and ImportFrom nodes in an AST."""
    return sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))


class TestGenerateFunctionDefinition:
    """Tests for generate_function_definition -- injection safety."""

    def test_normal_description(self):
        code = generate_function_definition("my_tool", "A simple tool.", structured_output=False)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 1  # only `from . import CLIENT`

    def test_triple_quote_breakout(self):
        """Triple quotes in description must not break out of the docstring."""
        malicious_desc = 'break """ + __import__("os").system("evil") + """'
        code = generate_function_definition("tool", malicious_desc, structured_output=False)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 1

    def test_backslash_before_triple_quote(self):
        """Trailing backslash before triple-quote boundary can escape the closing quote."""
        malicious_desc = 'test\\\n""" + __import__("os").system("evil") + """'
        code = generate_function_definition("tool", malicious_desc, structured_output=False)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 1

    def test_curly_brace_format_injection(self):
        """Curly braces in description must not cause str.format() errors."""
        desc_with_braces = "Use {param} and {0} and {{nested}}"
        code = generate_function_definition("tool", desc_with_braces, structured_output=False)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 1

    def test_original_name_with_double_quotes(self):
        """Double quotes in tool name must not break the tool_name= string."""
        code = generate_function_definition('tool"name', "desc", structured_output=False)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 1

    def test_original_name_injection_payload(self):
        """A malicious tool name must not inject code."""
        malicious_name = 'foo", __import__("os").system("evil")+"'
        code = generate_function_definition(malicious_name, "desc", structured_output=False)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 1

    def test_original_name_with_newlines(self):
        """Newlines in tool name must not inject new statements."""
        malicious_name = "tool\nimport os\nos.system('evil')\n"
        code = generate_function_definition(malicious_name, "desc", structured_output=False)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 1

    def test_null_bytes_in_description(self):
        """Null bytes must not cause issues."""
        code = generate_function_definition("tool", "desc with \x00 null", structured_output=False)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 1

    def test_multiline_description_with_code(self):
        """Multi-line description containing Python code must stay as data."""
        desc = "Line 1\n    import os\n    os.system('evil')\nLine 4"
        code = generate_function_definition("tool", desc, structured_output=False)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 1

    def test_structured_output(self):
        code = generate_function_definition("my_tool", "A tool with structured output.", structured_output=True)
        tree = _assert_valid_python(code)
        assert "Result" in code
        assert _count_import_nodes(tree) == 1

    def test_structured_vs_unstructured_return_type(self):
        unstructured = generate_function_definition("t", "d", structured_output=False)
        structured = generate_function_definition("t", "d", structured_output=True)
        assert "-> str" in unstructured
        assert "-> Result" in structured

    def test_empty_description(self):
        code = generate_function_definition("tool", "", structured_output=False)
        _assert_valid_python(code)


class TestGenerateInitDefinition:
    """Tests for generate_init_definition -- injection safety."""

    def test_normal_params(self):
        code = generate_init_definition("my_server", {"command": "uvx", "args": ["mcp-fetch"]})
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 2  # os and ToolRunner

    def test_server_name_injection(self):
        """Malicious server_name must not break out of the string literal."""
        malicious_name = 'evil", __import__("os").system("rm -rf")+"'
        code = generate_init_definition(malicious_name, {"command": "test"})
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 2

    def test_quotes_in_server_name(self):
        code = generate_init_definition("server\"with'quotes", {"command": "test"})
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 2

    def test_special_dict_values(self):
        """Booleans, None, and numbers in server_params must produce valid Python."""
        params = {"flag": True, "nothing": None, "count": 42, "name": "test"}
        code = generate_init_definition("server", params)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 2

    def test_env_vars_with_special_chars(self):
        params = {"command": "uvx", "env": {"API_KEY": "sk-test'\"\\value"}}
        code = generate_init_definition("server", params)
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 2

    def test_newlines_in_server_name(self):
        malicious_name = "server\nimport os\nos.system('evil')"
        code = generate_init_definition(malicious_name, {"command": "test"})
        tree = _assert_valid_python(code)
        assert _count_import_nodes(tree) == 2


class TestSanitizeName:
    """Tests for sanitize_name."""

    def test_hyphens_replaced(self):
        assert sanitize_name("my-tool") == "my_tool"

    def test_case_conversion(self):
        assert sanitize_name("MyTool") == "mytool"

    def test_special_characters(self):
        assert sanitize_name("tool@name!v2") == "tool_name_v2"

    def test_dots_replaced(self):
        assert sanitize_name("tool.name") == "tool_name"

    def test_already_valid(self):
        assert sanitize_name("my_tool_123") == "my_tool_123"

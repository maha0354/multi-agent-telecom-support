import pytest

from app.tools.calculator import calculate


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("18 / 30 * 10 * 129", 774.0),
        ("(399 - 249) / 2", 75.0),
        ("-5 + 3", -2),
        ("min(774, 399, 599 - 299)", 300),
        ("round(10 / 3, 1)", 3.3),
    ],
)
def test_valid_expressions(expression, expected):
    assert calculate(expression)["result"] == expected


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo hi')",
        "open('secrets.txt')",
        "2 ** 1000000",
        "x + 1",
        "'a' * 3",
        "1 +",
    ],
)
def test_rejects_unsafe_or_invalid(expression):
    result = calculate(expression)
    assert "error" in result and "result" not in result


def test_division_by_zero():
    assert calculate("1 / 0")["error"] == "Division by zero"


def test_overlong_expression():
    assert "error" in calculate("1+" * 150 + "1")

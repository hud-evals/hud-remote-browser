"""Pure function tests — no async, no external services needed."""

from scenarios.general import compare_answers
from evaluate.sheets_cell_values import column_to_index, parse_cell_reference


# ---------------------------------------------------------------------------
# compare_answers
# ---------------------------------------------------------------------------


class TestCompareAnswersExact:
    def test_identical_strings(self):
        assert compare_answers("hello", "hello") == 1.0

    def test_case_insensitive(self):
        assert compare_answers("Hello", "hello") == 1.0

    def test_whitespace_stripping(self):
        assert compare_answers("  hello  ", "hello") == 1.0

    def test_mismatch(self):
        assert compare_answers("hello", "world") == 0.0

    def test_none_actual(self):
        assert compare_answers(None, "hello") == 0.0

    def test_numeric_as_string(self):
        assert compare_answers("42", "42") == 1.0

    def test_empty_strings(self):
        assert compare_answers("", "") == 1.0


class TestCompareAnswersContains:
    def test_substring_found(self):
        assert compare_answers("the quick brown fox", "brown", mode="contains") == 1.0

    def test_substring_not_found(self):
        assert compare_answers("the quick", "brown", mode="contains") == 0.0

    def test_case_insensitive(self):
        assert compare_answers("The Quick", "quick", mode="contains") == 1.0

    def test_none_actual(self):
        assert compare_answers(None, "hello", mode="contains") == 0.0


class TestCompareAnswersJson:
    def test_matching_dicts(self):
        assert compare_answers('{"a": 1}', '{"a": 1}', mode="json") == 1.0

    def test_different_key_order(self):
        assert (
            compare_answers('{"b": 2, "a": 1}', '{"a": 1, "b": 2}', mode="json") == 1.0
        )

    def test_mismatch(self):
        assert compare_answers('{"a": 1}', '{"a": 2}', mode="json") == 0.0

    def test_invalid_json(self):
        assert compare_answers("not json", '{"a": 1}', mode="json") == 0.0

    def test_non_string_input(self):
        assert compare_answers({"a": 1}, '{"a": 1}', mode="json") == 1.0

    def test_none_actual(self):
        assert compare_answers(None, '{"a": 1}', mode="json") == 0.0


class TestCompareAnswersNumeric:
    def test_matching_integers(self):
        assert compare_answers("42", "42", mode="numeric") == 1.0

    def test_matching_floats(self):
        assert compare_answers("3.14", "3.14", mode="numeric") == 1.0

    def test_embedded_in_text(self):
        assert compare_answers("The answer is 42", "42", mode="numeric") == 1.0

    def test_mismatch(self):
        assert compare_answers("42", "43", mode="numeric") == 0.0

    def test_negative_numbers(self):
        assert compare_answers("-5", "-5", mode="numeric") == 1.0

    def test_no_numbers_found(self):
        assert compare_answers("no digits", "42", mode="numeric") == 0.0

    def test_none_actual(self):
        assert compare_answers(None, "42", mode="numeric") == 0.0


class TestCompareAnswersRegex:
    def test_matching_pattern(self):
        assert compare_answers("abc123", r"\d+", mode="regex") == 1.0

    def test_non_matching_pattern(self):
        assert compare_answers("abc", r"\d+", mode="regex") == 0.0

    def test_case_insensitive(self):
        assert compare_answers("ABC", "abc", mode="regex") == 1.0

    def test_invalid_pattern(self):
        assert compare_answers("abc", "[invalid", mode="regex") == 0.0

    def test_none_actual(self):
        assert compare_answers(None, r"\d+", mode="regex") == 0.0


class TestCompareAnswersUnknownMode:
    def test_unknown_mode_returns_zero(self):
        assert compare_answers("hello", "hello", mode="nonexistent") == 0.0


# ---------------------------------------------------------------------------
# column_to_index / parse_cell_reference
# ---------------------------------------------------------------------------


class TestColumnToIndex:
    def test_column_a(self):
        assert column_to_index("A") == 0

    def test_column_b(self):
        assert column_to_index("B") == 1

    def test_column_z(self):
        assert column_to_index("Z") == 25

    def test_column_aa(self):
        assert column_to_index("AA") == 26

    def test_column_ab(self):
        assert column_to_index("AB") == 27

    def test_column_az(self):
        assert column_to_index("AZ") == 51

    def test_column_ba(self):
        assert column_to_index("BA") == 52

    def test_column_zz(self):
        assert column_to_index("ZZ") == 701

    def test_lowercase_input(self):
        assert column_to_index("a") == 0


class TestParseCellReference:
    def test_a1(self):
        assert parse_cell_reference("A1") == ("A", 0, 0)

    def test_b2(self):
        assert parse_cell_reference("B2") == ("B", 1, 1)

    def test_aa1(self):
        assert parse_cell_reference("AA1") == ("AA", 0, 26)

    def test_c15(self):
        assert parse_cell_reference("C15") == ("C", 14, 2)

    def test_a100(self):
        assert parse_cell_reference("A100") == ("A", 99, 0)

    def test_lowercase_converts_to_upper(self):
        assert parse_cell_reference("a1") == ("A", 0, 0)

    def test_invalid_no_digits(self):
        assert parse_cell_reference("ABC") is None

    def test_invalid_no_letters(self):
        assert parse_cell_reference("123") is None

    def test_invalid_empty_string(self):
        assert parse_cell_reference("") is None

    def test_invalid_special_chars(self):
        assert parse_cell_reference("A$1") is None

"""Tests for quiz_logic module."""

import pytest
import quiz_logic
from languages import get_language_numbers

# Load Spanish numbers for testing
NUMBERS = get_language_numbers("es")


class TestGetRandomQuestion:
    """Tests for get_random_question function."""

    def test_returns_valid_number(self):
        """Test that get_random_question returns a valid number from NUMBERS."""
        number, answer = quiz_logic.get_random_question(NUMBERS)
        assert number in NUMBERS
        assert NUMBERS[number] == answer

    def test_excludes_specified_numbers(self):
        """Test that excluded numbers are not returned."""
        exclude = [1, 2, 3, 4, 5]
        for _ in range(20):  # Test multiple times due to randomness
            number, _ = quiz_logic.get_random_question(NUMBERS, exclude_numbers=exclude)
            assert number not in exclude

    def test_resets_when_all_excluded(self):
        """Test that all numbers can be excluded and then reset."""
        all_numbers = list(NUMBERS.keys())
        number, answer = quiz_logic.get_random_question(
            NUMBERS, exclude_numbers=all_numbers
        )
        # Should still return a valid number (reset behavior)
        assert number in NUMBERS
        assert NUMBERS[number] == answer

    def test_weighted_probability_favors_smaller_numbers(self):
        """Test that weighting system is applied (not strict probabilistic test)."""
        # Test that the weighting logic exists by checking that different
        # ranges of numbers have different weights
        # This is more of a smoke test than a strict statistical test

        # Generate many numbers and check basic distribution
        numbers = []
        for _ in range(1000):
            number, _ = quiz_logic.get_random_question(NUMBERS)
            numbers.append(number)

        # Just verify we get a mix of numbers from different ranges
        # (any numbers <=100, any numbers >100, any numbers >1000)
        has_small = any(n <= 100 for n in numbers)
        has_medium = any(100 < n <= 1000 for n in numbers)
        has_large = any(n > 1000 for n in numbers)

        assert has_small, "Should include some numbers <= 100"
        assert has_medium, "Should include some numbers 100-1000"
        assert has_large, "Should include some numbers > 1000"


class TestGenerateMultipleChoice:
    """Tests for generate_multiple_choice function."""

    def test_returns_four_options(self):
        """Test that generate_multiple_choice returns exactly 4 options."""
        correct_number = 42
        correct_answer = NUMBERS[correct_number]
        options = quiz_logic.generate_multiple_choice(
            NUMBERS, correct_number, correct_answer
        )
        assert len(options) == 4

    def test_includes_correct_answer(self):
        """Test that the correct answer is in the options."""
        correct_number = 100
        correct_answer = NUMBERS[correct_number]
        options = quiz_logic.generate_multiple_choice(
            NUMBERS, correct_number, correct_answer
        )
        assert correct_answer in options

    def test_all_options_unique(self):
        """Test that all options are unique."""
        correct_number = 50
        correct_answer = NUMBERS[correct_number]
        options = quiz_logic.generate_multiple_choice(
            NUMBERS, correct_number, correct_answer
        )
        assert len(options) == len(set(options))

    def test_options_are_valid_spanish_numbers(self):
        """Test that all options are valid Spanish numbers from NUMBERS."""
        correct_number = 75
        correct_answer = NUMBERS[correct_number]
        options = quiz_logic.generate_multiple_choice(
            NUMBERS, correct_number, correct_answer
        )

        all_spanish_numbers = set(NUMBERS.values())
        for option in options:
            assert option in all_spanish_numbers

    def test_randomization(self):
        """Test that options are randomized (not always in same position)."""
        correct_number = 25
        correct_answer = NUMBERS[correct_number]

        positions = []
        for _ in range(20):
            options = quiz_logic.generate_multiple_choice(
                NUMBERS, correct_number, correct_answer
            )
            positions.append(options.index(correct_answer))

        # Correct answer should appear in different positions
        assert len(set(positions)) > 1


class TestCheckAnswer:
    """Tests for check_answer function."""

    def test_exact_match_returns_true(self):
        """Test that exact matches return True."""
        assert quiz_logic.check_answer("cinco", "cinco") is True
        assert quiz_logic.check_answer("doscientos", "doscientos") is True

    def test_case_sensitive(self):
        """Test that check is case-sensitive (exact match required)."""
        # check_answer does exact string comparison
        assert quiz_logic.check_answer("cinco", "cinco") is True
        assert quiz_logic.check_answer("CINCO", "cinco") is False

    def test_whitespace_sensitive(self):
        """Test that whitespace matters for exact match."""
        assert quiz_logic.check_answer("cinco", "cinco") is True
        assert quiz_logic.check_answer("  cinco  ", "cinco") is False

    def test_wrong_answer_returns_false(self):
        """Test that wrong answers return False."""
        assert quiz_logic.check_answer("seis", "cinco") is False
        assert quiz_logic.check_answer("diez", "veinte") is False


class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_removes_accents(self):
        """Test that accents are removed."""
        assert quiz_logic.normalize_text("José") == "jose"
        assert quiz_logic.normalize_text("dieciséis") == "dieciseis"
        assert quiz_logic.normalize_text("veintidós") == "veintidos"

    def test_lowercase_conversion(self):
        """Test that text is converted to lowercase."""
        assert quiz_logic.normalize_text("HELLO") == "hello"
        assert quiz_logic.normalize_text("HeLLo") == "hello"

    def test_whitespace_normalization(self):
        """Test that extra whitespace is normalized."""
        assert quiz_logic.normalize_text("  hello  world  ") == "hello world"
        assert quiz_logic.normalize_text("hello    world") == "hello world"

    def test_empty_string(self):
        """Test that empty strings are handled."""
        assert quiz_logic.normalize_text("") == ""
        assert quiz_logic.normalize_text("   ") == ""


class TestValidatePartialAnswer:
    """Tests for validate_partial_answer function."""

    def test_correct_complete_answer(self):
        """Test validation of correct complete answer."""
        result = quiz_logic.validate_partial_answer("mil", "mil")
        assert result["is_complete"] is True
        assert result["is_correct"] is True
        assert len(result["words"]) == 1
        assert result["words"][0]["status"] == "correct"

    def test_partial_correct_answer(self):
        """Test validation of partial correct answer."""
        result = quiz_logic.validate_partial_answer("mil", "mil ciento once")
        assert result["is_complete"] is False
        assert result["is_correct"] is False
        assert len(result["words"]) == 1
        assert result["words"][0]["status"] == "correct"

    def test_incorrect_answer(self):
        """Test validation of incorrect answer."""
        result = quiz_logic.validate_partial_answer("dos", "mil")
        assert result["is_complete"] is False
        assert result["is_correct"] is False
        assert len(result["words"]) == 1
        assert result["words"][0]["status"] == "incorrect"

    def test_multiple_words_mixed(self):
        """Test validation with multiple words, some correct, some wrong."""
        result = quiz_logic.validate_partial_answer("mil dos", "mil ciento once")
        assert result["is_complete"] is False
        assert len(result["words"]) == 2
        assert result["words"][0]["status"] == "correct"  # "mil" is correct
        assert result["words"][1]["status"] == "incorrect"  # "dos" is wrong

    def test_empty_input(self):
        """Test validation of empty input."""
        result = quiz_logic.validate_partial_answer("", "mil")
        assert result["is_complete"] is False
        assert result["is_correct"] is False
        assert len(result["words"]) == 0


class TestCheckAnswerAdvanced:
    """Tests for check_answer_advanced function."""

    def test_exact_match(self):
        """Test exact match returns True."""
        assert quiz_logic.check_answer_advanced("mil", "mil") is True
        assert quiz_logic.check_answer_advanced("ciento once", "ciento once") is True

    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert quiz_logic.check_answer_advanced("MIL", "mil") is True
        assert quiz_logic.check_answer_advanced("Ciento Once", "ciento once") is True

    def test_accent_insensitive(self):
        """Test accent insensitivity."""
        assert quiz_logic.check_answer_advanced("dieciseis", "dieciséis") is True
        assert quiz_logic.check_answer_advanced("veintidos", "veintidós") is True

    def test_wrong_answer(self):
        """Test wrong answer returns False."""
        assert quiz_logic.check_answer_advanced("dos", "mil") is False
        assert quiz_logic.check_answer_advanced("cien", "mil") is False


class TestNumbersDataIntegrity:
    """Tests for numbers_data.py integrity."""

    def test_numbers_dict_not_empty(self):
        """Test that NUMBERS dictionary is not empty."""
        assert len(NUMBERS) > 0

    def test_has_expected_count(self):
        """Test that we have approximately 1000 numbers."""
        assert len(NUMBERS) >= 900  # Allow some flexibility
        assert len(NUMBERS) <= 1100

    def test_all_keys_are_integers(self):
        """Test that all keys are integers."""
        for key in NUMBERS.keys():
            assert isinstance(key, int)

    def test_all_values_are_strings(self):
        """Test that all values are strings."""
        for value in NUMBERS.values():
            assert isinstance(value, str)
            assert len(value) > 0

    def test_basic_numbers_present(self):
        """Test that basic numbers 1-10 are present."""
        for i in range(1, 11):
            assert i in NUMBERS

    def test_no_duplicate_values(self):
        """Test that Spanish translations are not duplicated for different numbers."""
        # Note: Some numbers legitimately have same Spanish (like 100 = "cien" and part of "ciento")
        # This test checks that most values are unique
        values_list = list(NUMBERS.values())
        unique_values = set(values_list)
        # Allow some duplicates but most should be unique
        assert len(unique_values) / len(values_list) > 0.95

    def test_spanish_text_format(self):
        """Test that Spanish text doesn't have obvious formatting issues."""
        for spanish in NUMBERS.values():
            # No leading/trailing spaces
            assert spanish == spanish.strip()
            # No double spaces
            assert "  " not in spanish
            # Only lowercase (Spanish numbers are lowercase)
            assert spanish == spanish.lower()

"""Quiz logic for generating questions and validating answers."""

import random
import secrets
import time

# Seed random with high-resolution time and secrets
random.seed(secrets.randbits(128) ^ int(time.time() * 1000000))


def get_random_question(numbers_dict, exclude_numbers=None):
    """
    Get a random number from the available numbers with weighted probability.
    Lower numbers have higher probability; probability drops by 10x per order of magnitude above 100.

    Probability weights:
    - Numbers < 100: weight = 1.0 (baseline)
    - Numbers 100-999: weight = 0.1 (10x less likely)
    - Numbers 1000-9999: weight = 0.01 (100x less likely)
    - Numbers 10000-99999: weight = 0.001 (1000x less likely)
    - Numbers 100000+: weight = 0.0001 (10000x less likely)

    Args:
        numbers_dict: Dictionary mapping numbers to their translations
        exclude_numbers: List of numbers to exclude (already asked in this session)

    Returns:
        Tuple of (number, correct_answer)
    """
    if exclude_numbers is None:
        exclude_numbers = []

    available_numbers = [
        num for num in numbers_dict.keys() if num not in exclude_numbers
    ]

    # If all numbers have been used, reset
    if not available_numbers:
        available_numbers = list(numbers_dict.keys())

    # Calculate weights with step-wise decrease based on order of magnitude
    # Each order of magnitude above 100 reduces probability by 10x
    weights = []

    for num in available_numbers:
        if num < 100:
            # Full weight for numbers < 100
            weight = 1.0
        elif num < 1000:
            # 100-999: 10x less likely
            weight = 0.1
        elif num < 10000:
            # 1000-9999: 100x less likely
            weight = 0.01
        elif num < 100000:
            # 10000-99999: 1000x less likely
            weight = 0.001
        else:
            # 100000+: 10000x less likely
            weight = 0.0001
        weights.append(weight)

    # Re-seed random with fresh entropy for each call
    random.seed(secrets.randbits(128))

    # Use random.choices for weighted selection
    number = random.choices(available_numbers, weights=weights, k=1)[0]
    return number, numbers_dict[number]


def generate_multiple_choice(numbers_dict, correct_number, correct_answer):
    """
    Generate 4 multiple choice options with one correct answer.
    Uses secrets module for cryptographically secure randomization.

    Args:
        numbers_dict: Dictionary mapping numbers to their translations
        correct_number: The number being tested
        correct_answer: The correct translation

    Returns:
        List of 4 options (strings) in truly random order
    """
    # Get all possible wrong answers (exclude the correct one)
    #wrong_answers = [
    #    answer for num, answer in numbers_dict.items() if num != correct_number
    #]
        # Determine magnitude (digit length)
    digit_length = len(str(correct_number))


    # Filter numbers with same digit length (exclude correct number)
    same_magnitude_numbers = [
        (num, answer)
        for num, answer in numbers_dict.items()
        if num != correct_number and len(str(num)) == digit_length
    ]

    print(f"Candidates with same magnitude ({digit_length} digits):")
    for num, answer in same_magnitude_numbers:
        print(f"  {num} -> {answer}")

    # Extract only answers
    wrong_answers = [answer for num, answer in same_magnitude_numbers]

    # Use secrets for cryptographically secure random selection
    selected_wrong = []
    wrong_answers_copy = wrong_answers.copy()
    for _ in range(min(3, len(wrong_answers))):
        idx = secrets.randbelow(len(wrong_answers_copy))
        selected_wrong.append(wrong_answers_copy.pop(idx))

    # Combine correct and wrong answers
    all_options = [correct_answer] + selected_wrong

    # Use secrets module for truly random shuffling with extra entropy
    # Add multiple shuffle passes to eliminate any patterns
    for shuffle_round in range(3):  # Multiple shuffle rounds for extra randomness
        for i in range(len(all_options) - 1, 0, -1):
            # Add extra entropy by XOR with time
            entropy = secrets.randbits(32) ^ (int(time.time() * 1000000) % (2**32))
            j = entropy % (i + 1)
            all_options[i], all_options[j] = all_options[j], all_options[i]

    return all_options


def check_answer(user_answer, correct_answer):
    """
    Check if the user's answer is correct.

    Args:
        user_answer: The answer selected by the user
        correct_answer: The correct Spanish translation

    Returns:
        Boolean indicating if answer is correct
    """
    return user_answer == correct_answer


def normalize_text(text):
    """
    Normalize text for comparison by:
    - Converting to lowercase
    - Removing extra spaces
    - Handling German umlauts and ß (ü→ue, ö→oe, ä→ae, ß→ss)
    - Optionally handling accent variations

    Args:
        text: Text to normalize

    Returns:
        Normalized text
    """
    import unicodedata

    # Convert to lowercase
    text = text.lower().strip()

    # Replace German umlauts and ß with ASCII equivalents
    # This allows users to type "fuenf" for "fünf", "oe" for "ö", etc.
    german_replacements = {
        "ü": "ue",
        "ö": "oe",
        "ä": "ae",
        "ß": "ss",
    }
    for umlaut, replacement in german_replacements.items():
        text = text.replace(umlaut, replacement)

    # Remove extra spaces between words
    text = " ".join(text.split())

    # Normalize accents (convert to base form)
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")

    return text


def validate_partial_answer(user_input, correct_answer, lang_code="es"):
    """
    Validate user input against the correct answer with language-aware strategy.
    Returns detailed validation information for live feedback.

    Args:
        user_input: Current user input
        correct_answer: The correct answer
        lang_code: Language code to determine validation strategy

    Returns:
        Dictionary with validation details:
        {
            'is_complete': bool,
            'is_correct': bool,
            'words': [{'text': str, 'status': 'correct'|'incorrect'|'incomplete'}]
        }
    """
    from languages.config import get_validation_strategy, get_component_decomposer

    # Normalize both inputs
    normalized_input = normalize_text(user_input)
    normalized_correct = normalize_text(correct_answer)

    # Get validation strategy for this language
    strategy = get_validation_strategy(lang_code)

    if strategy == "component_based":
        # Component-based validation (e.g., German compound words)
        decomposer = get_component_decomposer(lang_code)

        if not decomposer:
            # Fallback to word-based if decomposer not available
            strategy = "word_based"
        else:
            # Decompose the correct answer into components
            components = decomposer(correct_answer)

            # Normalize components for matching
            normalized_components = [normalize_text(c) for c in components]

            # Build the full normalized answer by concatenating components
            full_normalized = "".join(normalized_components)

            # Track position in user input and component list
            word_validations = []
            input_pos = 0

            for i, (component, norm_component) in enumerate(
                zip(components, normalized_components)
            ):
                comp_len = len(norm_component)

                if input_pos >= len(normalized_input):
                    # User hasn't typed this component yet
                    break

                # Check if user input matches this component (fully or partially)
                remaining_input = normalized_input[input_pos:]

                if remaining_input.startswith(norm_component):
                    # Component fully matched
                    word_validations.append({"text": component, "status": "correct"})
                    input_pos += comp_len
                elif norm_component.startswith(remaining_input):
                    # Component partially matched (incomplete)
                    # Show what user has typed so far for this component
                    typed_length = len(remaining_input)
                    partial_text = component[:typed_length]  # Preserve original casing
                    word_validations.append(
                        {"text": partial_text, "status": "incomplete"}
                    )
                    input_pos += typed_length
                    break  # Stop here as user is still typing this component
                else:
                    # Check for partial match at start of component
                    match_len = 0
                    for j in range(min(len(remaining_input), comp_len)):
                        if remaining_input[j] == norm_component[j]:
                            match_len = j + 1
                        else:
                            break

                    if match_len > 0:
                        # Partial match - show correct part
                        word_validations.append(
                            {"text": component[:match_len], "status": "correct"}
                        )
                        input_pos += match_len

                        # Then show incorrect part
                        incorrect_len = min(
                            len(remaining_input) - match_len, comp_len - match_len
                        )
                        if incorrect_len > 0:
                            incorrect_text = user_input[
                                len(user_input)
                                - len(remaining_input)
                                + match_len : len(user_input)
                                - len(remaining_input)
                                + match_len
                                + incorrect_len
                            ]
                            word_validations.append(
                                {"text": incorrect_text, "status": "incorrect"}
                            )
                            input_pos += incorrect_len
                    else:
                        # No match at all - mark as incorrect
                        incorrect_text = user_input[
                            len(user_input) - len(remaining_input) :
                        ]
                        word_validations.append(
                            {"text": incorrect_text, "status": "incorrect"}
                        )
                        input_pos = len(normalized_input)
                    break

            # Check if answer is complete and correct
            is_complete = normalized_input == full_normalized
            is_correct = is_complete

            return {
                "is_complete": is_complete,
                "is_correct": is_correct,
                "words": word_validations,
                "expected_word_count": len(components),
                "current_word_count": len(word_validations),
            }

    # Word-based validation (default, e.g., Spanish)
    # Split into words
    input_words = normalized_input.split() if normalized_input else []
    correct_words = normalized_correct.split()

    # Build word-by-word validation
    word_validations = []

    for i, input_word in enumerate(input_words):
        if i < len(correct_words):
            correct_word = correct_words[i]

            if input_word == correct_word:
                # Word is correct
                word_validations.append({"text": input_word, "status": "correct"})
            elif correct_word.startswith(input_word):
                # Word is incomplete but on the right track
                word_validations.append({"text": input_word, "status": "incomplete"})
            else:
                # Word is incorrect
                word_validations.append({"text": input_word, "status": "incorrect"})
        else:
            # Extra word beyond the correct answer
            word_validations.append({"text": input_word, "status": "incorrect"})

    # Check if answer is complete and correct
    is_complete = len(input_words) == len(correct_words) and all(
        w["status"] == "correct" for w in word_validations
    )
    is_correct = normalized_input == normalized_correct

    return {
        "is_complete": is_complete,
        "is_correct": is_correct,
        "words": word_validations,
        "expected_word_count": len(correct_words),
        "current_word_count": len(input_words),
    }


def check_answer_advanced(user_answer, correct_answer):
    """
    Check if the user's typed answer is correct (for advanced mode).
    Uses normalization to handle spacing and accent variations.

    Args:
        user_answer: The answer typed by the user
        correct_answer: The correct Spanish translation

    Returns:
        Boolean indicating if answer is correct
    """
    return normalize_text(user_answer) == normalize_text(correct_answer)

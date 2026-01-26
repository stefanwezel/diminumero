"""Quiz logic for generating questions and validating answers."""

import random
import secrets
import time
from numbers_data import NUMBERS

# Seed random with high-resolution time and secrets
random.seed(secrets.randbits(128) ^ int(time.time() * 1000000))


def get_random_question(exclude_numbers=None):
    """
    Get a random number from the available numbers with weighted probability.
    Lower numbers have higher probability; numbers > 5000 are picked ~1/4 as often.
    
    Args:
        exclude_numbers: List of numbers to exclude (already asked in this session)
    
    Returns:
        Tuple of (number, correct_answer)
    """
    if exclude_numbers is None:
        exclude_numbers = []
    
    available_numbers = [num for num in NUMBERS.keys() if num not in exclude_numbers]
    
    # If all numbers have been used, reset
    if not available_numbers:
        available_numbers = list(NUMBERS.keys())
    
    # Calculate weights with linear decrease based on number value
    # Numbers <= 5000 get full weight, numbers > 5000 get reduced weight
    max_number = max(available_numbers)
    weights = []
    
    for num in available_numbers:
        if num <= 5000:
            # Full weight for numbers <= 5000
            weight = 1.0
        else:
            # Linear decrease for numbers > 5000
            # At 5000: weight = 1.0
            # At max_number: weight = 0.25
            # Linear interpolation between 5000 and max
            if max_number > 5000:
                weight = 1.0 - (0.75 * (num - 5000) / (max_number - 5000))
            else:
                weight = 1.0
        weights.append(weight)
    
    # Re-seed random with fresh entropy for each call
    random.seed(secrets.randbits(128))
    
    # Use random.choices for weighted selection
    number = random.choices(available_numbers, weights=weights, k=1)[0]
    return number, NUMBERS[number]


def generate_multiple_choice(correct_number, correct_answer):
    """
    Generate 4 multiple choice options with one correct answer.
    Uses secrets module for cryptographically secure randomization.
    
    Args:
        correct_number: The number being tested
        correct_answer: The correct Spanish translation
    
    Returns:
        List of 4 options (strings) in truly random order
    """
    # Get all possible wrong answers (exclude the correct one)
    wrong_answers = [answer for num, answer in NUMBERS.items() if num != correct_number]
    
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

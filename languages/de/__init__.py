"""German language module for diminumero."""

from .numbers import NUMBERS

__all__ = ["NUMBERS", "decompose_german_number"]


def decompose_german_number(number_text):
    """
    Decompose a German compound number into its component parts.

    For example: "Siebenundvierzig" -> ["Sieben", "und", "vierzig"]

    Uses greedy left-to-right matching with known German number components.
    Preserves the original casing from the input.

    Args:
        number_text: German number as string (e.g., "Siebenundvierzig")

    Returns:
        List of component strings with original casing preserved
    """
    # Define all known German number components (lowercase for matching)
    # Note: Uses proper German spellings with umlauts (ü, ö, ä, ß)
    # User input with ASCII equivalents (ue, oe, ae, ss) is handled by normalize_text()
    components = [
        # Single digits (various forms)
        "null",
        "eins",
        "ein",
        "eine",
        "zwei",
        "drei",
        "vier",
        "fünf",
        "sechs",
        "sieben",
        "acht",
        "neun",
        # Teens (special cases)
        "zehn",
        "elf",
        "zwölf",
        "dreizehn",
        "vierzehn",
        "fünfzehn",
        "sechzehn",
        "siebzehn",
        "achtzehn",
        "neunzehn",
        # Tens
        "zwanzig",
        "dreißig",
        "dreissig",  # Alternative spelling
        "vierzig",
        "fünfzig",
        "sechzig",
        "siebzig",
        "achtzig",
        "neunzig",
        # Scales
        "hundert",
        "tausend",
        "million",
        "millionen",
        "milliarde",
        "milliarden",
        # Connector
        "und",
    ]

    # Sort by length (descending) for greedy matching
    # This ensures "sechzehn" matches as one unit, not "sechs" + "zehn"
    components_sorted = sorted(components, key=len, reverse=True)

    result = []
    position = 0

    while position < len(number_text):
        matched = False

        # Try to match the longest possible component
        for component in components_sorted:
            component_len = len(component)

            # Check if we have enough characters left
            if position + component_len <= len(number_text):
                # Extract slice and compare (case-insensitive)
                slice_text = number_text[position : position + component_len]

                if slice_text.lower() == component:
                    # Match found - preserve original casing from input
                    result.append(slice_text)
                    position += component_len
                    matched = True
                    break

        if not matched:
            # Character doesn't match any component - skip it or group as unknown
            # For now, we'll skip unrecognized characters
            position += 1

    return result

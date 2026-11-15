"""Legacy variant generation for fault catalog demos."""

import os


def generate_half_even_variant(source_path: str, output_path: str) -> int:
    """
    Generate HALF_EVEN variant from correct Java source.
    
    Reads Java source, replaces all "RoundingMode.HALF_UP" with
    "RoundingMode.HALF_EVEN", writes to output_path.
    
    Args:
        source_path: Path to correct Java source file
        output_path: Path to write variant (under build/)
    
    Returns:
        Number of replacements made
    
    Raises:
        ValueError: If no "RoundingMode.HALF_UP" found in source
    """
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace all occurrences
    new_content = content.replace('RoundingMode.HALF_UP', 'RoundingMode.HALF_EVEN')
    
    # Check if any replacement was made
    count = content.count('RoundingMode.HALF_UP')
    if count == 0:
        raise ValueError(f"No 'RoundingMode.HALF_UP' found in {source_path}")
    
    # Create parent directory if needed
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return count

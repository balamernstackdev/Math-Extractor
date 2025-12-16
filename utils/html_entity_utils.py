"""Utilities for handling HTML entities in MathML conversion."""
from __future__ import annotations

import re
import html
from typing import Optional

# Import the auto-generated entity mappings
try:
    from utils.entity_mapper import (
        ENTITY_TO_CHAR,
        CHAR_TO_ENTITY,
        HEX_TO_CHAR,
        DECIMAL_TO_CHAR,
    )
except ImportError:
    # Fallback if entity_mapper.py doesn't exist
    ENTITY_TO_CHAR: dict[str, str] = {}
    CHAR_TO_ENTITY: dict[str, str] = {}
    HEX_TO_CHAR: dict[str, str] = {}
    DECIMAL_TO_CHAR: dict[str, str] = {}


def decode_html_entity(entity: str) -> Optional[str]:
    """
    Decode an HTML entity to its Unicode character.
    
    Args:
        entity: HTML entity like "&alpha;", "&#x03B1;", or "&#945;"
    
    Returns:
        Unicode character or None if not found
    """
    if not entity:
        return None
    
    entity = entity.strip()
    
    # Named entity: &alpha;
    if entity.startswith('&') and entity.endswith(';') and '#' not in entity:
        entity_name = entity[1:-1]  # Remove & and ;
        return ENTITY_TO_CHAR.get(entity_name)
    
    # Hex entity: &#x03B1; or &#x03B1
    hex_match = re.match(r'&#x([0-9A-Fa-f]+);?', entity)
    if hex_match:
        hex_code = hex_match.group(1)
        if hex_code in HEX_TO_CHAR:
            return HEX_TO_CHAR[hex_code]
        try:
            return chr(int(hex_code, 16))
        except (ValueError, OverflowError):
            return None
    
    # Decimal entity: &#945; or &#945
    decimal_match = re.match(r'&#(\d+);?', entity)
    if decimal_match:
        decimal_code = decimal_match.group(1)
        if decimal_code in DECIMAL_TO_CHAR:
            return DECIMAL_TO_CHAR[decimal_code]
        try:
            return chr(int(decimal_code))
        except (ValueError, OverflowError):
            return None
    
    return None


def encode_to_html_entity(char: str, use_named: bool = True) -> Optional[str]:
    """
    Encode a Unicode character to its HTML entity.
    
    Args:
        char: Unicode character
        use_named: If True, prefer named entities (e.g., &alpha;) over numeric
    
    Returns:
        HTML entity string or None if not found
    """
    if not char or len(char) != 1:
        return None
    
    if use_named and char in CHAR_TO_ENTITY:
        return CHAR_TO_ENTITY[char]
    
    # Fallback to numeric entity
    code_point = ord(char)
    return f'&#x{code_point:04X};'


def decode_html_entities(text: str) -> str:
    """
    Decode all HTML entities in a string.
    
    Args:
        text: String potentially containing HTML entities
    
    Returns:
        String with entities decoded to Unicode characters
    """
    if not text:
        return text
    
    # First, try using Python's html.unescape for standard entities
    try:
        text = html.unescape(text)
    except Exception:
        pass
    
    # Then handle custom entities from our reference
    # Pattern to match HTML entities: &name; or &#x...; or &#...;
    pattern = r'&(?:[a-zA-Z][a-zA-Z0-9]+|#x[0-9A-Fa-f]+|#\d+);?'
    
    def replace_entity(match: re.Match) -> str:
        entity = match.group(0)
        decoded = decode_html_entity(entity)
        return decoded if decoded else entity
    
    return re.sub(pattern, replace_entity, text)


def escape_for_mathml(text: str) -> str:
    """
    Escape special characters for MathML XML.
    
    Args:
        text: Text to escape
    
    Returns:
        Escaped text safe for MathML
    """
    if not text:
        return text
    
    # Escape XML special characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    
    return text


def normalize_mathml_entities(mathml: str) -> str:
    """
    Normalize HTML entities in MathML to ensure proper rendering.
    
    This function:
    1. Decodes HTML entities to Unicode where appropriate
    2. Escapes XML special characters
    3. Ensures MathML-safe encoding
    
    Args:
        mathml: MathML string potentially containing entities
    
    Returns:
        Normalized MathML string
    """
    if not mathml:
        return mathml
    
    # For MathML, we want to keep mathematical entities as Unicode
    # but ensure XML safety
    
    # First decode any HTML entities in text content
    # (but preserve MathML tags)
    parts = []
    i = 0
    while i < len(mathml):
        # Find next tag
        tag_start = mathml.find('<', i)
        if tag_start == -1:
            # No more tags, process remaining text
            remaining = mathml[i:]
            decoded = decode_html_entities(remaining)
            parts.append(escape_for_mathml(decoded))
            break
        
        # Process text before tag
        if tag_start > i:
            text_before = mathml[i:tag_start]
            decoded = decode_html_entities(text_before)
            parts.append(escape_for_mathml(decoded))
        
        # Find tag end
        tag_end = mathml.find('>', tag_start)
        if tag_end == -1:
            # Malformed, just append rest
            parts.append(mathml[tag_start:])
            break
        
        # Append tag as-is
        tag = mathml[tag_start:tag_end + 1]
        parts.append(tag)
        
        i = tag_end + 1
    
    return ''.join(parts)


def get_entity_reference(char: str) -> Optional[dict]:
    """
    Get full entity reference information for a character.
    
    Args:
        char: Unicode character
    
    Returns:
        Dictionary with entity information or None
    """
    if not char or len(char) != 1:
        return None
    
    # Check if we have a named entity
    entity_name = None
    for name, mapped_char in ENTITY_TO_CHAR.items():
        if mapped_char == char:
            entity_name = name
            break
    
    if not entity_name:
        return None
    
    code_point = ord(char)
    return {
        'char': char,
        'unicode': f'U+{code_point:04X}',
        'entity_name': entity_name,
        'html_entity': f'&{entity_name};',
        'hex_entity': f'&#x{code_point:04X};',
        'decimal_entity': f'&#{code_point};',
    }


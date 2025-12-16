# HTML Entity Integration in MathML Conversion

## Overview

The HTML entity reference system has been **fully integrated** into the MathML conversion pipeline. The system now properly handles HTML entities (like `&alpha;`, `&#x03B1;`, `&#945;`) when converting LaTeX to MathML.

## Integration Points

### 1. Main Conversion Flow (`convert` method)

- **After successful LaTeX conversion**: The MathML output is normalized using `normalize_mathml_entities()` to ensure all HTML entities are properly decoded and XML-safe.

```python
# Post-process to add Mathpix-like structure
result = self._enhance_mathml(result, equation_label)

# Normalize HTML entities in MathML for proper rendering
if ENTITY_UTILS_AVAILABLE:
    result = normalize_mathml_entities(result)
```

### 2. Text Content Handling

- **Plain text in `\text{}`**: HTML entities are decoded before escaping for XML
- **Fallback text content**: When LaTeX conversion fails, HTML entities in the fallback text are properly handled

```python
# Decode HTML entities if present, then escape for XML
if ENTITY_UTILS_AVAILABLE:
    text_content = decode_html_entities(text_content)
    text_content = escape_for_mathml(text_content)
```

### 3. MathML Enhancement (`_enhance_mathml` method)

- **Final normalization**: After enhancing MathML structure, entities are normalized one final time to ensure consistency

```python
# Normalize HTML entities in the final MathML
if ENTITY_UTILS_AVAILABLE:
    mathml_str = normalize_mathml_entities(mathml_str)
```

## Features

### ✅ Automatic Entity Decoding

The system automatically decodes HTML entities to Unicode characters:
- `&alpha;` → `α`
- `&#x03B1;` → `α`
- `&#945;` → `α`

### ✅ XML Safety

All text content is properly escaped for XML/MathML:
- `&` → `&amp;`
- `<` → `&lt;`
- `>` → `&gt;`
- `"` → `&quot;`
- `'` → `&apos;`

### ✅ Graceful Fallback

If entity utilities are not available, the system falls back to basic XML escaping, ensuring the conversion still works.

## Supported Entity Formats

1. **Named entities**: `&alpha;`, `&beta;`, `&gamma;`, etc.
2. **Hex entities**: `&#x03B1;`, `&#x03B2;`, etc.
3. **Decimal entities**: `&#945;`, `&#946;`, etc.

## Example Usage

### Before Integration
```python
# HTML entities would remain as-is or be incorrectly escaped
latex = "\\text{&alpha; + &beta;}"
# Result: <mtext>&alpha; + &beta;</mtext>  ❌
```

### After Integration
```python
# HTML entities are automatically decoded
latex = "\\text{&alpha; + &beta;}"
# Result: <mtext>α + β</mtext>  ✅
```

## Testing

To test the integration:

```python
from services.ocr.latex_to_mathml import LatexToMathML

converter = LatexToMathML()

# Test with HTML entities in text
latex = "\\text{The value of &alpha; is &lt; 1}"
mathml = converter.convert(latex)
# Should properly decode &alpha; and escape < as &lt;

# Test with LaTeX that converts to MathML with entities
latex = "\\alpha + \\beta"
mathml = converter.convert(latex)
# Should produce proper MathML with Unicode characters
```

## Benefits

1. **Better OCR handling**: OCR output that includes HTML entities is properly converted
2. **Improved compatibility**: MathML with proper Unicode characters renders better across platforms
3. **Comprehensive support**: 937 entities from the reference are supported
4. **Automatic processing**: No manual intervention needed - entities are handled automatically

## Files Modified

- `services/ocr/latex_to_mathml.py`: Integrated entity utilities throughout the conversion pipeline

## Dependencies

- `utils/html_entity_utils.py`: Entity handling utilities
- `utils/entity_mapper.py`: Entity reference dictionaries (auto-generated)

## Status

✅ **Fully Integrated and Ready to Use**

The entity reference system is now fully integrated into the MathML conversion pipeline and will automatically handle HTML entities in all conversion scenarios.


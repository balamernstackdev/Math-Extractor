# OCR MathML Cleaner Module

A comprehensive Python module for cleaning corrupted OCR MathML and converting it to clean LaTeX and MathML formats.

## Features

✅ **Removes stray OCR characters**: €, é, ¢, », etc.  
✅ **Fixes nested repeated tags**: `<mi><mi>x</mi></mi>` → `<mi>x</mi>`  
✅ **Removes empty subscripts/superscripts**: Automatically cleans empty elements  
✅ **Extracts mathematical elements**: Variables, subscripts, superscripts, operators  
✅ **Converts to clean LaTeX**: Outputs properly formatted LaTeX equations  
✅ **Converts to clean MathML**: Outputs valid, well-formed MathML  
✅ **Handles common OCR patterns**: "l é ]" → "[l]", etc.

## Quick Start

```python
from services.ocr.ocr_mathml_cleaner import OCRMathMLCleaner

# Initialize cleaner
cleaner = OCRMathMLCleaner()

# Clean corrupted MathML
corrupted_mathml = '''
<math xmlns="http://www.w3.org/1998/Math/MathML">
    <mi>x</mi>
    <mo>€</mo>
    <mi>y</mi>
    <mo>é</mo>
</math>
'''

result = cleaner.clean(corrupted_mathml)

# Access results
print("Clean LaTeX:", result["latex"])
print("Clean MathML:", result["mathml"])
print("Extracted elements:", result["elements"])
```

## API Reference

### `OCRMathMLCleaner`

Main class for cleaning OCR MathML.

#### Methods

##### `clean(corrupted_mathml: str) -> dict[str, str]`

Cleans corrupted OCR MathML and returns clean LaTeX and MathML.

**Parameters:**
- `corrupted_mathml` (str): Corrupted MathML string from OCR

**Returns:**
- `dict` with keys:
  - `"latex"`: Clean LaTeX equation string
  - `"mathml"`: Clean MathML string
  - `"elements"`: Dictionary of extracted elements:
    - `"variables"`: List of variable names
    - `"subscripts"`: List of dicts with `"base"` and `"subscript"` keys
    - `"superscripts"`: List of dicts with `"base"` and `"superscript"` keys
    - `"operators"`: List of operator symbols

**Example:**
```python
result = cleaner.clean(corrupted_mathml)
latex = result["latex"]  # "x + y = z"
mathml = result["mathml"]  # Clean MathML XML
variables = result["elements"]["variables"]  # ["x", "y", "z"]
```

## Cleaning Features

### 1. Stray Character Removal

Removes common OCR error characters:
- Currency symbols: €, £, ¥, ¢
- Accented characters: é, à, è, ù, ô, î, ç, ñ
- Special symbols: », «, §, ©, ®, ™, etc.

### 2. OCR Pattern Correction

Fixes common OCR misreadings:
- `"l é ]"` → `"[l]"`
- Accented characters → plain ASCII
- Greek letters → LaTeX commands (α → alpha, π → pi, etc.)

### 3. Structure Cleaning

- **Removes empty elements**: Tags with no content
- **Flattens nested duplicates**: `<mi><mi>x</mi></mi>` → `<mi>x</mi>`
- **Removes empty subscripts/superscripts**: Cleans up malformed math structures

### 4. Element Extraction

Automatically extracts:
- **Variables**: Mathematical identifiers (x, y, z, h, etc.)
- **Subscripts**: Base and subscript pairs
- **Superscripts**: Base and superscript pairs
- **Operators**: Mathematical operators (+, -, =, ≤, ≥, etc.)

### 5. LaTeX Conversion

Converts cleaned MathML to LaTeX:
- Fractions: `<mfrac>` → `\frac{}{}`
- Subscripts: `<msub>` → `_{}`
- Superscripts: `<msup>` → `^{}`
- Square roots: `<msqrt>` → `\sqrt{}`
- Operators: Special symbols → LaTeX commands

## Examples

### Example 1: Basic Cleaning

```python
from services.ocr.ocr_mathml_cleaner import OCRMathMLCleaner

cleaner = OCRMathMLCleaner()

corrupted = '''
<math xmlns="http://www.w3.org/1998/Math/MathML">
    <mi>x</mi>
    <mo>€</mo>
    <mi>y</mi>
</math>
'''

result = cleaner.clean(corrupted)
# result["latex"] = "x + y"  (€ removed)
# result["mathml"] = Clean MathML without €
```

### Example 2: Nested Tags

```python
corrupted = '''
<math xmlns="http://www.w3.org/1998/Math/MathML">
    <mi><mi>x</mi></mi>
    <mo>+</mo>
    <mi><mi>y</mi></mi>
</math>
'''

result = cleaner.clean(corrupted)
# Nested <mi> tags are flattened
```

### Example 3: Empty Subscripts

```python
corrupted = '''
<math xmlns="http://www.w3.org/1998/Math/MathML">
    <msub>
        <mi>x</mi>
        <mi></mi>
    </msub>
</math>
'''

result = cleaner.clean(corrupted)
# Empty msub is removed
```

### Example 4: Complex Equation

```python
corrupted = '''
<math xmlns="http://www.w3.org/1998/Math/MathML">
    <mfrac>
        <mrow>
            <mi>a</mi>
            <mo>€</mo>
            <mi>b</mi>
        </mrow>
        <mrow>
            <mi>c</mi>
            <mo>é</mo>
            <mi>d</mi>
        </mrow>
    </mfrac>
    <mo>=</mo>
    <msub>
        <mi>x</mi>
        <mn>1</mn>
    </msub>
</math>
'''

result = cleaner.clean(corrupted)
# result["latex"] = "\\frac{a + b}{c + d} = x_{1}"
# result["elements"]["subscripts"] = [{"base": "x", "subscript": "1"}]
```

## Integration

### With Existing MathPix Clone

The cleaner can be integrated into the OCR pipeline:

```python
from services.ocr.ocr_mathml_cleaner import OCRMathMLCleaner
from services.ocr.image_to_latex import ImageToLatex
from services.ocr.latex_to_mathml import LatexToMathML

# After OCR
latex_ocr = ImageToLatex()
latex = latex_ocr.image_to_latex(image_path)

# Convert to MathML
latex_to_mathml = LatexToMathML()
mathml = latex_to_mathml.convert(latex)

# Clean if corrupted
cleaner = OCRMathMLCleaner()
cleaned = cleaner.clean(mathml)

# Use cleaned output
clean_latex = cleaned["latex"]
clean_mathml = cleaned["mathml"]
```

## Testing

Run tests:
```bash
pytest tests/test_ocr_cleaner.py -v
```

Run example:
```bash
python examples/ocr_cleaner_example.py
```

## Error Handling

The module handles:
- **Malformed XML**: Falls back to text-based cleaning
- **Parse errors**: Gracefully handles invalid MathML
- **Empty input**: Returns empty strings
- **Missing elements**: Skips missing parts gracefully

## Performance

- **Fast**: Uses efficient XML parsing with ElementTree
- **Memory efficient**: Processes elements in-place when possible
- **Robust**: Multiple fallback strategies for edge cases

## Limitations

- Some complex MathML structures may require manual correction
- Very malformed XML may not be fully recoverable
- Some OCR patterns may need custom rules for specific use cases

## Contributing

To add new OCR patterns, edit the `OCR_PATTERNS` list in `ocr_mathml_cleaner.py`:

```python
OCR_PATTERNS = [
    (r"pattern_to_match", "replacement"),
    # Add your patterns here
]
```

## License

Part of the MathPix Clone project.


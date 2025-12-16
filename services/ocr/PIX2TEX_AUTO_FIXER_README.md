# Pix2Tex LaTeX Auto-Fixer Agent

A comprehensive Cursor agent that automatically fixes bad LaTeX extracted from math images using pix2tex OCR.

## Features

- **Pix2Tex OCR Integration**: Uses `pix2tex[api]` for high-quality LaTeX extraction from math images
- **Image Preprocessing**: Automatic deskew, resize, and contrast enhancement using OpenCV
- **LaTeX Validation**: Detects common corruption patterns:
  - Unbalanced braces
  - Double subscripts (e.g., `x_{a_{b}}`)
  - Letter-by-letter subscripts (e.g., `m_{a}t_{h}r_{m}`)
  - Broken command fragments (e.g., `\f_{r}`, `\s_{u}m`)
- **Automated Repairs**: Iterative fixing of common OCR errors:
  - Collapses letter-by-letter patterns to `\mathrm{word}`
  - Fixes broken `\ldots` tokens
  - Repairs empty fraction numerators
  - Normalizes command spacing
  - Fixes broken command patterns (`\f_{r}a_{c}` → `\frac`)
- **MathML Conversion**: Converts validated LaTeX to MathML
- **Comprehensive Logging**: Detailed telemetry for debugging

## Installation

The required dependencies are already in `requirements.txt`:

```bash
pip install pix2tex[api] opencv-python pillow latex2mathml
```

## Usage

### Basic Usage

```python
from services.ocr.pix2tex_auto_fixer import Pix2TexAutoFixer, fix_and_convert

# Option 1: Using the convenience function
result = fix_and_convert("path/to/math_image.png")

# Option 2: Using the class directly
fixer = Pix2TexAutoFixer()
result = fixer.fix_and_convert("path/to/math_image.png")
```

### Result Format

The function returns a dictionary with the following structure:

```python
{
    'status': 'ok' | 'fixed' | 'failed',
    'latex': str,           # Clean LaTeX (if successful)
    'mathml': str,           # MathML string (if successful)
    'latex_raw': str,        # Raw LaTeX from OCR (if failed)
    'suggestion': str,       # Human-friendly correction prompt (if failed)
    'log': list[tuple]       # List of (event, data) log entries
}
```

### Status Values

- **`'ok'`**: LaTeX was valid from OCR, no fixes needed
- **`'fixed'`**: LaTeX was corrupted but successfully auto-fixed
- **`'failed'`**: Auto-fix failed, manual correction needed

### Example

```python
from services.ocr.pix2tex_auto_fixer import fix_and_convert

result = fix_and_convert("tests/image.png", max_fix_attempts=4)

if result['status'] == 'ok':
    print(f"Perfect! LaTeX: {result['latex']}")
    print(f"MathML: {result['mathml']}")
elif result['status'] == 'fixed':
    print(f"Fixed! LaTeX: {result['latex']}")
    print(f"MathML: {result['mathml']}")
else:
    print(f"Failed. Raw LaTeX: {result['latex_raw']}")
    print(f"Suggestion: {result['suggestion']}")
```

## Command Line Interface

The agent includes a CLI for testing:

```bash
python services/ocr/pix2tex_auto_fixer.py tests/image.png [max_attempts]
```

Example:
```bash
python services/ocr/pix2tex_auto_fixer.py tests/image.png 4
```

## Integration with Existing Services

### Integration with ImageToLatex

You can use the auto-fixer as a post-processing step:

```python
from services.ocr.image_to_latex import ImageToLatex
from services.ocr.pix2tex_auto_fixer import Pix2TexAutoFixer

# Get raw OCR
image_to_latex = ImageToLatex()
raw_latex = image_to_latex.image_to_latex("image.png")

# Auto-fix and convert to MathML
fixer = Pix2TexAutoFixer()
# Note: You'd need to modify fixer to accept LaTeX directly
# For now, use the image path
result = fixer.fix_and_convert("image.png")
```

### Integration with LatexToMathML

The auto-fixer can be used before MathML conversion:

```python
from services.ocr.pix2tex_auto_fixer import fix_and_convert
from services.ocr.latex_to_mathml import LatexToMathML

# Get fixed LaTeX
result = fix_and_convert("image.png")

if result['status'] in ('ok', 'fixed'):
    # Use the fixed LaTeX
    latex = result['latex']
    
    # Or use the MathML directly
    mathml = result['mathml']
    
    # Or convert again with LatexToMathML for additional processing
    converter = LatexToMathML()
    mathml = converter.convert(latex)
```

## Common Fixes

The agent automatically fixes:

1. **Letter-by-letter subscripts**: `m_{a}t_{h}r_{m}` → `\mathrm{math}`
2. **Broken commands**: `\f_{r}a_{c}` → `\frac`
3. **Empty fractions**: `\frac{}{n}` → `\frac{1}{n}`
4. **Broken tokens**: `\ldotsy` → `\ldots`
5. **Double commands**: `\left\left` → `\left`
6. **Command spacing**: `\mathrm {text}` → `\mathrm{text}`
7. **Unbalanced braces**: Attempts to fix or reports error

## Configuration

### Adjusting Fix Attempts

```python
result = fix_and_convert(
    "image.png",
    max_fix_attempts=6  # More attempts for complex corruptions
)
```

### Image Preprocessing

The preprocessing can be customized by modifying the `preprocess_image` method:

- `target_size`: Default 1024 (longest side)
- Deskew threshold: Currently 0.1 degrees
- Contrast enhancement: Uses `ImageOps.autocontrast`

## Error Handling

The agent handles:

- Missing pix2tex installation (graceful fallback with error)
- Missing latex2mathml (raises RuntimeError)
- Image loading errors (returns failed status)
- OCR failures (returns failed status with error log)
- Conversion failures (attempts fixes, then returns suggestion)

## Logging

All operations are logged using the project's logger (`core.logger`). The result dictionary also includes a `log` field with detailed telemetry:

```python
for event, data in result['log']:
    print(f"{event}: {data}")
```

Common log events:
- `preprocess`: Image preprocessing status
- `pix2tex_raw`: Raw LaTeX from OCR
- `validation_failed`: Validation failure reason
- `fix_attempt_N`: Fix attempt details
- `mathml`: MathML conversion status
- `suggestion`: Human correction prompt

## Cursor Agent Prompt

When using this in Cursor, you can use:

```
Run the Pix2Tex LaTeX Auto-Fixer on the selected region(s). 
For each region, return the cleaned LaTeX, MathML, and a short log. 
If automatic repair fails, produce a human-edit prompt.
```

## Limitations

- Requires pix2tex installation for OCR
- Some complex corruptions may require manual intervention
- MathML conversion depends on latex2mathml library
- Image preprocessing assumes grayscale/color images (not specialized formats)

## Future Enhancements

Potential improvements:
- Direct LaTeX input (not just images)
- Integration with LLM-based correction for complex cases
- More sophisticated brace balancing
- Support for equation arrays and multi-line formulas
- Custom fix patterns via configuration

## See Also

- `services/ocr/latex_to_mathml.py`: MathML conversion service
- `services/ocr/image_to_latex.py`: Image to LaTeX OCR service
- `services/ocr/latex_reconstructor.py`: LaTeX reconstruction utilities
- `services/ocr/dynamic_latex_reconstructor.py`: Dynamic LaTeX reconstruction


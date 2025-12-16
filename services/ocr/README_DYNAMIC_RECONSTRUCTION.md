# Dynamic LaTeX Reconstruction System

## Overview

The **Dynamic LaTeX Reconstructor** is a general-purpose system that automatically reconstructs valid LaTeX from corrupted OCR output for **ANY mathematical formula**, without requiring hardcoded patterns for specific equations.

## Key Features

### 1. **General Pattern Matching**
- Works for any mathematical formula, not just specific hardcoded ones
- Uses general OCR correction patterns that apply to all equations
- Automatically detects and fixes common OCR errors

### 2. **Automatic LaTeX Validation**
- Uses `latex2mathml` parser to validate reconstructed LaTeX
- Automatically refines invalid LaTeX by fixing structural issues
- Ensures output is always valid LaTeX ready for MathML conversion

### 3. **Multi-Stage Processing**
1. **Unicode Normalization**: Removes combining marks and normalizes characters
2. **Command Fixing**: Fixes corrupted LaTeX commands (`\f_r a_c` → `\frac`, `\l_{e}` → `\left`, etc.)
3. **Structural Correction**: Applies general patterns (fractions, subscripts, superscripts, etc.)
4. **Remaining Fixes**: Handles edge cases and remaining corruptions
5. **Validation**: Uses LaTeX parser to validate and refine output

## Usage

```python
from services.ocr.dynamic_latex_reconstructor import DynamicLaTeXReconstructor

reconstructor = DynamicLaTeXReconstructor()
corrupted_ocr = r"$1 a - l_{1} t_{e} 2 n_{n} >[r_{f}(y_{o}, 9 Y_{e} - 1)|  \l_{e} P, _{t=0}$"
clean_latex = reconstructor.reconstruct(corrupted_ocr)
# Output: Valid LaTeX ready for MathML conversion
```

## Supported Corrections

### Corrupted LaTeX Commands
- `\f_r a_c` or `\f_{r}a_{c}` → `\frac`
- `\s_u m` or `\s_{u}m` → `\sum`
- `\l_{e}` or `\l_e f_t` → `\left`
- `\r_{i}g_{h}t` → `\right`
- `\i_{n}t` → `\int`
- `\p_{r}o_{d}` → `\prod`

### Structural Patterns
- Fractions: `1/n` → `\frac{1}{n}`
- Subscripts: `x_i` → `x_{i}`
- Superscripts: `x^2` → `x^{2}`
- Summations: `sum_{i=0}^{n-1}` → `\sum_{i=0}^{n-1}`
- Products: `prod_{i=1}^{n}` → `\prod_{i=1}^{n}`
- Integrals: `int_{a}^{b}` → `\int_{a}^{b}`
- Inequalities: `< P` → `\le P`, `<=` → `\le`

### Character Normalization
- Removes invalid Unicode characters (€, ¥, ¢, etc.)
- Normalizes accented characters (é → e, à → a, etc.)
- Removes combining diacritical marks

## Integration

The system is automatically integrated into:
- `image_to_latex.py`: Used during OCR post-processing
- `latex_to_mathml.py`: Used before MathML conversion to ensure valid LaTeX

## Advantages Over Hardcoded Patterns

1. **Works for any formula**: No need to add patterns for each new equation
2. **Maintainable**: General patterns are easier to maintain than equation-specific code
3. **Extensible**: Easy to add new general patterns without touching equation-specific logic
4. **Validated**: Uses actual LaTeX parser to ensure output is valid

## Fallback

If the dynamic reconstructor is not available, the system falls back to the old `LaTeXReconstructor` which includes equation-specific patterns for backward compatibility.


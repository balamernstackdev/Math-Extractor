# Complex Equation Test Cases

This document contains test cases for validating the Hybrid AST Pipeline with various equation types.

## How to Test

1. Paste these equations into a PDF or image
2. Use the app to select and OCR each equation
3. Verify the rendered output matches the expected result
4. Check that MathML is valid (green "Valid" badge)

---

## 1. Simple Equations

### Test 1.1: Basic Arithmetic
**LaTeX Input:**
```latex
x + y = 2
```

**Expected Output:**
- Rendered: `x + y = 2`
- MathML: Contains `<mi>x</mi> <mo>+</mo> <mi>y</mi> <mo>=</mo> <mn>2</mn>`
- Status: Valid ✅

### Test 1.2: Subscripts and Superscripts
**LaTeX Input:**
```latex
x_1 + x_2^{2} = y
```

**Expected Output:**
- Rendered: `x₁ + x₂² = y`
- MathML: Contains `<msub>`, `<msup>` tags
- Status: Valid ✅

---

## 2. Fractions

### Test 2.1: Simple Fraction
**LaTeX Input:**
```latex
\frac{a}{b} = \frac{c}{d}
```

**Expected Output:**
- Rendered: Proper fraction display
- MathML: Contains `<mfrac><mi>a</mi><mi>b</mi></mfrac>`
- Status: Valid ✅

### Test 2.2: Nested Fraction
**LaTeX Input:**
```latex
\frac{1}{1 + \frac{1}{x}}
```

**Expected Output:**
- Rendered: Nested fraction structure
- MathML: Nested `<mfrac>` tags
- Status: Valid ✅

### Test 2.3: Complex Fraction
**LaTeX Input:**
```latex
\frac{x^2 + 2x + 1}{x - 1} = x + 3 + \frac{4}{x - 1}
```

**Expected Output:**
- Rendered: Numerator and denominator with proper spacing
- MathML: `<mfrac>` with complex children
- Status: Valid ✅

---

## 3. Roots and Radicals

### Test 3.1: Square Root
**LaTeX Input:**
```latex
\sqrt{x^2 + y^2} = r
```

**Expected Output:**
- Rendered: √(x² + y²) = r
- MathML: `<msqrt>` with proper content
- Status: Valid ✅

### Test 3.2: N-th Root
**LaTeX Input:**
```latex
\sqrt[3]{27} = 3
```

**Expected Output:**
- Rendered: ∛27 = 3
- MathML: `<mroot>` with index and content
- Status: Valid ✅

---

## 4. Summations and Products

### Test 4.1: Basic Summation
**LaTeX Input:**
```latex
\sum_{i=1}^{n} i = \frac{n(n+1)}{2}
```

**Expected Output:**
- Rendered: Σ with i=1 below and n above
- MathML: `<munderover>` or `<msubsup>` with ∑
- Status: Valid ✅

### Test 4.2: Product
**LaTeX Input:**
```latex
\prod_{k=1}^{n} k = n!
```

**Expected Output:**
- Rendered: Π with k=1 below and n above
- MathML: Proper product notation
- Status: Valid ✅

### Test 4.3: Nested Summation
**LaTeX Input:**
```latex
\sum_{i=1}^{m} \sum_{j=1}^{n} a_{ij}
```

**Expected Output:**
- Rendered: Double summation with indices
- MathML: Nested `<munderover>` structures
- Status: Valid ✅

---

## 5. Matrices

### Test 5.1: 2x2 Matrix
**LaTeX Input:**
```latex
\begin{pmatrix} a & b \\ c & d \end{pmatrix}
```

**Expected Output:**
- Rendered: 2x2 matrix with parentheses
- MathML: `<mtable>` with `<mtr>` and `<mtd>`
- Status: Valid ✅

### Test 5.2: 3x3 Matrix
**LaTeX Input:**
```latex
\begin{bmatrix} 1 & 0 & 0 \\ 0 & 1 & 0 \\ 0 & 0 & 1 \end{bmatrix}
```

**Expected Output:**
- Rendered: Identity matrix with brackets
- MathML: `<mtable>` with 3 rows
- Status: Valid ✅

---

## 6. Integrals

### Test 6.1: Definite Integral
**LaTeX Input:**
```latex
\int_{a}^{b} f(x) \, dx = F(b) - F(a)
```

**Expected Output:**
- Rendered: ∫ with a below and b above
- MathML: `<msubsup>` with ∫ operator
- Status: Valid ✅

### Test 6.2: Double Integral
**LaTeX Input:**
```latex
\iint_{D} f(x,y) \, dA
```

**Expected Output:**
- Rendered: ∬ over region D
- MathML: Proper integral notation
- Status: Valid ✅

---

## 7. Greek Letters and Symbols

### Test 7.1: Greek Alphabet
**LaTeX Input:**
```latex
\alpha, \beta, \gamma, \delta, \theta, \lambda, \mu, \pi, \sigma, \omega
```

**Expected Output:**
- Rendered: α, β, γ, δ, θ, λ, μ, π, σ, ω
- MathML: Unicode Greek letters in `<mi>` tags
- Status: Valid ✅

### Test 7.2: Set Theory
**LaTeX Input:**
```latex
A \cup B \cap C \subset D \in \mathbb{R}
```

**Expected Output:**
- Rendered: A ∪ B ∩ C ⊂ D ∈ ℝ
- MathML: Proper set operators
- Status: Valid ✅

---

## 8. Complex Real-World Equations

### Test 8.1: Quadratic Formula
**LaTeX Input:**
```latex
x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
```

**Expected Output:**
- Rendered: Complete quadratic formula
- MathML: Nested `<mfrac>`, `<msqrt>`, `<msup>`
- Status: Valid ✅

### Test 8.2: Euler's Formula
**LaTeX Input:**
```latex
e^{i\pi} + 1 = 0
```

**Expected Output:**
- Rendered: e^(iπ) + 1 = 0
- MathML: Superscript with Greek letter
- Status: Valid ✅

### Test 8.3: Signal Processing (From Your Test)
**LaTeX Input:**
```latex
Y_j[t] = \sum_{i \in \mathbb{Z}_0} h_{i,j}[t]X_i[t] + Z_j[t]
```

**Expected Output:**
- Rendered: Complete signal equation with summation
- MathML: Complex structure with subscripts, summation, set notation
- Status: Valid ✅

### Test 8.4: Probability
**LaTeX Input:**
```latex
P(A|B) = \frac{P(B|A)P(A)}{P(B)}
```

**Expected Output:**
- Rendered: Conditional probability (Bayes' theorem)
- MathML: Fraction with conditional notation
- Status: Valid ✅

---

## 9. Known Limitations

### ⚠️ Multiline Equations
**LaTeX Input:**
```latex
\begin{align}
x + y &= 2 \\
x - y &= 0
\end{align}
```

**Current Status:**
- Parser may flatten to single line
- Future enhancement needed for alignment detection

### ⚠️ Cases/Piecewise
**LaTeX Input:**
```latex
f(x) = \begin{cases}
  x^2 & \text{if } x \geq 0 \\
  -x^2 & \text{if } x < 0
\end{cases}
```

**Current Status:**
- Basic cases support
- Text handling may need refinement

---

## Test Results Template

Use this template to record test results:

| Test ID | Equation | Recognition | MathML Valid | Visual Match | Notes |
|---------|----------|-------------|--------------|--------------|-------|
| 1.1 | x + y = 2 | ✅ | ✅ | ✅ | Perfect |
| 1.2 | x_1 + x_2^2 | ✅ | ✅ | ✅ | Subscripts work |
| 2.1 | Fraction | ✅ | ✅ | ✅ | Clean structure |
| ... | ... | ... | ... | ... | ... |

---

## Automated Testing

Run the test suite:
```bash
python -m pytest tests/test_ast_pipeline.py -v
```

Expected: All 18 tests pass ✅

---

## Reporting Issues

If a test fails:
1. Note the equation that failed
2. Capture the MathML output
3. Check logs for parsing errors
4. Open an issue with:
   - Test case number
   - Expected vs. actual output
   - Log snippet

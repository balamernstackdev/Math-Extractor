# HTML Entity Reference for MathML Conversion

This directory contains a comprehensive reference of HTML entities extracted from `Entity_RS.html`, specifically organized for MathML conversion.

## Files

- **`entity_reference.json`**: Complete JSON database of all 937 entities with:
  - Unicode character
  - Entity name (e.g., `alpha`, `Aacute`)
  - Hex code (e.g., `&#x03B1;`)
  - Decimal code (e.g., `&#945;`)
  - Categorized by type (Greek letters, operators, arrows, etc.)

- **`entity_mapper.py`**: Python dictionaries for easy lookup:
  - `ENTITY_TO_CHAR`: Map entity names to Unicode characters
  - `CHAR_TO_ENTITY`: Map Unicode characters to entity names
  - `HEX_TO_CHAR`: Map hex codes to Unicode characters
  - `DECIMAL_TO_CHAR`: Map decimal codes to Unicode characters

- **`html_entity_utils.py`**: Utility functions for entity handling:
  - `decode_html_entity()`: Convert HTML entity to Unicode
  - `encode_to_html_entity()`: Convert Unicode to HTML entity
  - `decode_html_entities()`: Decode all entities in a string
  - `escape_for_mathml()`: Escape XML special characters
  - `normalize_mathml_entities()`: Normalize entities in MathML
  - `get_entity_reference()`: Get full entity info for a character

## Usage Examples

### Decoding HTML Entities

```python
from utils.html_entity_utils import decode_html_entity, decode_html_entities

# Decode a single entity
char = decode_html_entity("&alpha;")  # Returns: "α"
char = decode_html_entity("&#x03B1;")  # Returns: "α"
char = decode_html_entity("&#945;")  # Returns: "α"

# Decode all entities in a string
text = "&alpha; + &beta; = &gamma;"
decoded = decode_html_entities(text)  # Returns: "α + β = γ"
```

### Encoding to HTML Entities

```python
from utils.html_entity_utils import encode_to_html_entity

# Encode a character
entity = encode_to_html_entity("α", use_named=True)  # Returns: "&alpha;"
entity = encode_to_html_entity("α", use_named=False)  # Returns: "&#x03B1;"
```

### Normalizing MathML

```python
from utils.html_entity_utils import normalize_mathml_entities

mathml = '<math><mi>&alpha;</mi><mo>+</mo><mi>&beta;</mi></math>'
normalized = normalize_mathml_entities(mathml)
# Converts entities to Unicode and ensures XML safety
```

### Direct Dictionary Access

```python
from utils.entity_mapper import ENTITY_TO_CHAR, CHAR_TO_ENTITY

# Look up character by entity name
char = ENTITY_TO_CHAR.get('alpha')  # Returns: "α"

# Look up entity by character
entity = CHAR_TO_ENTITY.get('α')  # Returns: "&alpha;"
```

## Categories

The entities are categorized for easy reference:

- **Greek Letters** (97): α, β, γ, δ, ε, ζ, η, θ, ι, κ, λ, μ, ν, ξ, ο, π, ρ, σ, τ, υ, φ, χ, ψ, ω (and uppercase)
- **Math Operators** (45): +, −, ×, ÷, ⋅, ∗, ∑, ∏, ∫, ∮, ∂, ∇, ∞, √, etc.
- **Arrows** (47): ←, →, ↑, ↓, ⇐, ⇒, ⇔, etc.
- **Relations** (94): =, ≠, <, >, ≤, ≥, ≈, ≡, ≅, ∼, ∝, ⊂, ⊃, ∈, ∋, etc.
- **Sets** (26): ∅, ∈, ∋, ⊂, ⊃, ∪, ∩, ∖, etc.
- **Other** (662): Accents, punctuation, Cyrillic, special symbols, etc.

## Regenerating the Reference

To regenerate the entity reference from `Entity_RS.html`:

```bash
python utils/parse_entity_reference.py
```

This will:
1. Parse `tests/Entity_RS.html`
2. Extract all entity mappings
3. Generate `entity_reference.json` and `entity_mapper.py`

## Integration with MathML Conversion

The entity utilities can be integrated into the LaTeX to MathML conversion pipeline:

```python
from utils.html_entity_utils import decode_html_entities, normalize_mathml_entities

# In your MathML conversion code:
def convert_to_mathml(latex: str) -> str:
    # ... convert LaTeX to MathML ...
    mathml = "<math>...</math>"
    
    # Normalize any HTML entities in the MathML
    mathml = normalize_mathml_entities(mathml)
    
    return mathml
```

## Notes

- All entities are case-sensitive (e.g., `&alpha;` vs `&Alpha;`)
- Some characters have multiple entity names (e.g., `&Delta;` and `&Dgr;` both map to Δ)
- The reference includes both standard HTML entities and extended mathematical entities
- Unicode characters are preferred in MathML for better compatibility


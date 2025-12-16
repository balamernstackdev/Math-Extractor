"""Parse Entity_RS.html to extract special character mappings for MathML conversion."""
import re
import html
from pathlib import Path
from typing import Dict, List, Tuple
import json


def parse_entity_html(html_file: str) -> Dict[str, Dict[str, str]]:
    """
    Parse Entity_RS.html and extract entity mappings.
    
    The HTML structure has:
    - Row 1: Characters (font tags with hex entities)
    - Row 2: Entity names (like &amp;Aacgr;)
    - Row 3: Hex codes (like &amp#x0386;)
    - Row 4: Decimal codes (like &amp;#902;)
    
    Returns a dictionary with:
    - entity_name: {unicode_char, hex_code, decimal_code, entity_name}
    """
    html_path = Path(html_file)
    if not html_path.exists():
        raise FileNotFoundError(f"File not found: {html_file}")
    
    content = html_path.read_text(encoding='utf-8', errors='ignore')
    
    entities = {}
    
    # Find all table rows
    rows = re.findall(r'<tr>.*?</tr>', content, re.DOTALL)
    
    i = 0
    while i < len(rows) - 3:
        # Check if this is a character row (has font size="7")
        char_row = rows[i]
        if '<font size="7">' not in char_row:
            i += 1
            continue
        
        # Extract all characters from this row
        char_cells = re.findall(r'<font size="7">(.*?)</font>', char_row)
        if not char_cells:
            i += 1
            continue
        
        # Next row should have entity names
        if i + 1 >= len(rows):
            break
        entity_row = rows[i + 1]
        entity_names = re.findall(r'<b>&amp;([^<]+);</b>', entity_row)
        
        # Next row should have hex codes
        if i + 2 >= len(rows):
            break
        hex_row = rows[i + 2]
        hex_codes = re.findall(r'&#x([0-9A-Fa-f]+);', hex_row)
        # Also try the format &amp#x...
        hex_codes_alt = re.findall(r'&amp#x([0-9A-Fa-f]+);', hex_row)
        if hex_codes_alt:
            hex_codes = hex_codes_alt
        
        # Next row should have decimal codes
        if i + 3 >= len(rows):
            break
        decimal_row = rows[i + 3]
        decimal_codes = re.findall(r'&#(\d+);', decimal_row)
        # Also try the format &amp;#...
        decimal_codes_alt = re.findall(r'&amp;#(\d+);', decimal_row)
        if decimal_codes_alt:
            decimal_codes = decimal_codes_alt
        
        # Match up the columns
        max_cols = min(len(char_cells), len(entity_names), len(hex_codes), len(decimal_codes))
        
        for col in range(max_cols):
            char_html = char_cells[col]
            entity_name = entity_names[col] if col < len(entity_names) else None
            hex_code = hex_codes[col] if col < len(hex_codes) else None
            decimal_code = decimal_codes[col] if col < len(decimal_codes) else None
            
            if not entity_name:
                continue
            
            # Decode HTML entities to get actual character
            try:
                char = html.unescape(char_html)
                # If still an entity, try to decode the hex
                if char.startswith('&#x'):
                    hex_val = char[3:-1]  # Remove &#x and ;
                    char = chr(int(hex_val, 16))
                elif char.startswith('&#'):
                    dec_val = char[2:-1]  # Remove &# and ;
                    char = chr(int(dec_val))
            except Exception:
                # Try to get character from hex code
                if hex_code:
                    try:
                        char = chr(int(hex_code, 16))
                    except:
                        continue
                elif decimal_code:
                    try:
                        char = chr(int(decimal_code))
                    except:
                        continue
                else:
                    continue
            
            if char and entity_name:
                entities[entity_name] = {
                    'char': char,
                    'unicode': f'U+{ord(char):04X}',
                    'hex': hex_code,
                    'decimal': decimal_code,
                    'entity_name': entity_name,
                    'html_entity': f'&{entity_name};',
                    'hex_entity': f'&#x{hex_code};' if hex_code else None,
                    'decimal_entity': f'&#{decimal_code};' if decimal_code else None,
                }
        
        # Move to next set of 4 rows
        i += 4
    
    return entities


def create_mathml_reference(entities: Dict) -> Dict[str, List[Dict]]:
    """
    Organize entities by category for MathML usage.
    """
    categories = {
        'greek_letters': [],
        'math_operators': [],
        'arrows': [],
        'relations': [],
        'sets': [],
        'accents': [],
        'punctuation': [],
        'other': []
    }
    
    # Greek letters (alpha, beta, gamma, etc.)
    greek_patterns = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 
                      'theta', 'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi', 'omicron',
                      'pi', 'rho', 'sigma', 'tau', 'upsilon', 'phi', 'chi', 'psi', 'omega',
                      'Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta',
                      'Theta', 'Iota', 'Kappa', 'Lambda', 'Mu', 'Nu', 'Xi', 'Omicron',
                      'Pi', 'Rho', 'Sigma', 'Tau', 'Upsilon', 'Phi', 'Chi', 'Psi', 'Omega']
    
    # Math operators
    operator_patterns = ['plus', 'minus', 'times', 'div', 'cdot', 'ast', 'star',
                        'sum', 'prod', 'int', 'oint', 'partial', 'nabla', 'infty',
                        'sqrt', 'root', 'frac', 'binom']
    
    # Arrows
    arrow_patterns = ['arrow', 'arr', 'Arrow', 'Arr', 'leftarrow', 'rightarrow', 
                     'uparrow', 'downarrow', 'Leftarrow', 'Rightarrow']
    
    # Relations
    relation_patterns = ['eq', 'ne', 'lt', 'gt', 'le', 'ge', 'approx', 'equiv',
                       'cong', 'sim', 'propto', 'subset', 'superset', 'in', 'ni']
    
    # Sets
    set_patterns = ['emptyset', 'in', 'ni', 'subset', 'superset', 'cup', 'cap',
                   'union', 'intersect', 'setminus']
    
    for entity_name, data in entities.items():
        name_lower = entity_name.lower()
        char = data['char']
        
        entry = {
            'entity': entity_name,
            'char': char,
            'unicode': data['unicode'],
            'hex': data['hex'],
            'decimal': data['decimal'],
            'html_entity': data['html_entity'],
            'hex_entity': data['hex_entity'],
            'decimal_entity': data['decimal_entity'],
        }
        
        categorized = False
        
        # Check Greek letters
        if any(pattern in name_lower for pattern in greek_patterns):
            categories['greek_letters'].append(entry)
            categorized = True
        
        # Check operators
        if any(pattern in name_lower for pattern in operator_patterns):
            categories['math_operators'].append(entry)
            categorized = True
        
        # Check arrows
        if any(pattern in name_lower for pattern in arrow_patterns):
            categories['arrows'].append(entry)
            categorized = True
        
        # Check relations
        if any(pattern in name_lower for pattern in relation_patterns):
            categories['relations'].append(entry)
            categorized = True
        
        # Check sets
        if any(pattern in name_lower for pattern in set_patterns):
            categories['sets'].append(entry)
            categorized = True
        
        if not categorized:
            categories['other'].append(entry)
    
    return categories


def main():
    """Parse Entity_RS.html and create reference files."""
    html_file = Path(__file__).parent.parent / 'tests' / 'Entity_RS.html'
    
    print(f"Parsing {html_file}...")
    entities = parse_entity_html(str(html_file))
    print(f"Found {len(entities)} entities")
    
    # Create categorized reference
    categories = create_mathml_reference(entities)
    
    # Save as JSON
    output_json = Path(__file__).parent / 'entity_reference.json'
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump({
            'all_entities': entities,
            'categories': categories,
            'total_count': len(entities)
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {output_json}")
    
    # Create a Python mapping file for easy import
    output_py = Path(__file__).parent / 'entity_mapper.py'
    with open(output_py, 'w', encoding='utf-8') as f:
        f.write('"""HTML entity to Unicode character mapping for MathML conversion."""\n\n')
        f.write('# Auto-generated from Entity_RS.html\n\n')
        f.write('ENTITY_TO_CHAR: dict[str, str] = {\n')
        for entity_name, data in sorted(entities.items()):
            char = data['char']
            # Use repr() to properly escape all special characters
            char_repr = repr(char)[1:-1]  # Remove quotes from repr, keeps proper escaping
            
            f.write(f"    '{entity_name}': {repr(char)},  # {data['unicode']}\n")
        f.write('}\n\n')
        
        f.write('CHAR_TO_ENTITY: dict[str, str] = {\n')
        for entity_name, data in sorted(entities.items(), key=lambda x: x[1]['char']):
            char = data['char']
            # Use repr() to properly escape all special characters
            char_repr = repr(char)
            
            f.write(f"    {char_repr}: '&{entity_name};',  # {entity_name}\n")
        f.write('}\n\n')
        
        f.write('HEX_TO_CHAR: dict[str, str] = {\n')
        for entity_name, data in sorted(entities.items()):
            if data['hex']:
                char = data['char']
                f.write(f"    '{data['hex']}': {repr(char)},  # {entity_name}\n")
        f.write('}\n\n')
        
        f.write('DECIMAL_TO_CHAR: dict[str, str] = {\n')
        for entity_name, data in sorted(entities.items()):
            if data['decimal']:
                char = data['char']
                f.write(f"    '{data['decimal']}': {repr(char)},  # {entity_name}\n")
        f.write('}\n')
    
    print(f"Saved to {output_py}")
    
    # Print summary
    print("\n=== Summary ===")
    print(f"Total entities: {len(entities)}")
    print(f"Greek letters: {len(categories['greek_letters'])}")
    print(f"Math operators: {len(categories['math_operators'])}")
    print(f"Arrows: {len(categories['arrows'])}")
    print(f"Relations: {len(categories['relations'])}")
    print(f"Sets: {len(categories['sets'])}")
    print(f"Other: {len(categories['other'])}")


if __name__ == '__main__':
    main()


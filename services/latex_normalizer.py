import re

def normalize_latex(text: str) -> str:
    # Wrap arguments for r_v^{(t)}(...)
    text = re.sub(
        r"r\((.*?)\)",
        r"r_v^{(t)}(\1)",
        text
    )

    # Add square for power terms
    if "[" in text and "]" in text:
        text = text.replace("]", "]^2")

    # Ensure inequality uses \le
    text = text.replace("< P", r"\le P")

    # Final cleanup
    text = text.strip()
    return text

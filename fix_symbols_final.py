import os
path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Mass fix for \n commands
# We search for r' followed by a newline and then some text
text = text.replace("r'\n" + "eg': '¬'", "r'\\neg': '¬'")
text = text.replace("r'\n" + "abla'", "r'\\nabla'")
text = text.replace("r'\n" + "eq'", "r'\\neq'")
text = text.replace("r'\n" + "u'", "r'\\nu'")
text = text.replace("r'\n" + "exists'", "r'\\nexists'")
text = text.replace("r'\n" + "otin'", "r'\\notin'")

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

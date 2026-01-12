import os
path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace("r'\n" + "exists'", "r'\\nexists'")

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

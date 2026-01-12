lines = open(r'services\ocr\latex_parser.py', 'r', encoding='utf-8').readlines()
for i, l in enumerate(lines[400:450], start=400):
    if 'token.startswith' in l and 'frac' in l:
        print(f'{i}: {repr(l)}')

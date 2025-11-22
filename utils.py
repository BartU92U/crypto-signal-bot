import json
import logging

SYMBOLS_FILE = 'monitored_symbols.json'

def load_symbols():
    try:
        with open(SYMBOLS_FILE, 'r') as f:
            data = json.load(f)
            return data.get('symbols', [])
    except FileNotFoundError:
        return []

def save_symbols(symbols):
    with open(SYMBOLS_FILE, 'w') as f:
        json.dump({'symbols': symbols}, f, indent=4)

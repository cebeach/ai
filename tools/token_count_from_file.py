#!/usr/bin/env python3
import sys
from pathlib import Path
import tiktoken

def main():
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    enc = tiktoken.get_encoding("o200k_base")
    print(len(enc.encode(text)))

if __name__ == "__main__":
    main()

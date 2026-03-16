#!/usr/bin/env python3
import sys
import tiktoken

def main():
    text = sys.stdin.read()
    enc = tiktoken.get_encoding("o200k_base")
    print(len(enc.encode(text)))

if __name__ == "__main__":
    main()

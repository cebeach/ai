
# Plan for Reimplementing `tiktoken.get_encoding("o200k_base")` Using Only Python Standard Library

## 1. Objective

Implement a pure-Python replacement for the behavior of:

```python
tiktoken.get_encoding("o200k_base")
```

using **only Python standard library dependencies**, while preserving the ability to:

- tokenize text into token IDs
- compute token counts
- optionally decode token IDs back to text

The primary motivating use case is token counting equivalent to:

```python
tiktoken.get_encoding("o200k_base").encode(text)
```

with no external dependencies.

---

# 2. Scope

The implementation must support:

- `get_encoding("o200k_base")`
- `.encode(text)` → `list[int]`
- token count computation
- optional `.decode(tokens)`

The implementation must **not depend on**:

- `tiktoken`
- Rust extensions
- third-party Python packages

Allowed modules include:

```
json
base64
re
functools
array
bisect
hashlib
typing
pathlib
collections
```

---

# 3. Core Constraint

Reimplementing the runtime algorithm is feasible with the standard library.

However the encoding **data** used by `o200k_base` must be provided explicitly.

This data includes:

- token merge rules
- token ranks
- regex pretokenization pattern
- special token mappings

These cannot be reconstructed algorithmically and must be **exported once** from a reference implementation.

Therefore the system consists of two components:

1. Pure-Python tokenizer engine
2. Serialized `o200k_base` encoding data

---

# 4. System Architecture

The reimplementation should be structured into four layers.

```
API layer
Encoding registry
Tokenizer engine
Encoding data
```

---

# 5. Proposed Project Layout

```
pure_tiktoken/
    __init__.py
    registry.py
    encoding.py
    bpe.py
    special.py
    data/
        o200k_base.json

tests/
    test_parity.py

tools/
    export_o200k_base.py
```

---

# 6. Public API

Provide a minimal compatible API.

### `get_encoding`

```
get_encoding(name: str) -> Encoding
```

Supported name:

```
"o200k_base"
```

---

### `Encoding` class

```
class Encoding:

    def encode(
        self,
        text: str,
        allowed_special=set(),
        disallowed_special="all"
    ) -> list[int]

    def decode(self, tokens: list[int]) -> str

    def decode_bytes(self, tokens: list[int]) -> bytes
```

Minimal requirement:

```
encode(text)
```

---

# 7. Encoding Specification Loader

The encoding should be stored as JSON.

Example structure:

```json
{
  "name": "o200k_base",
  "pat_str": "...",
  "mergeable_ranks": {
    "YQ==": 64
  },
  "special_tokens": {
    "<|endoftext|>": 199999
  }
}
```

### Notes

- JSON keys must be strings
- byte sequences are encoded using **base64**

At runtime:

```
base64 → bytes
```

The loader constructs:

```
dict[bytes, int]  mergeable_ranks
dict[str, int]    special_tokens
```

Reverse maps must also be built for decoding.

---

# 8. Regex Pretokenization

The encoding provides a regex pattern:

```
pat_str
```

Steps:

1. Compile the pattern

```
re.compile(pat_str)
```

2. Iterate matches over input text

3. For each match:

```
match_text → UTF-8 bytes → BPE encode
```

The regex pattern must be preserved exactly.

### Compatibility risk

If the original implementation relies on the third-party `regex` package, parity must be verified with Python's `re` module.

---

# 9. Special Token Handling

Special tokens must be recognized before normal tokenization.

Example:

```
<|endoftext|>
```

Workflow:

1. Build regex matching all special tokens.
2. Scan input text.
3. Split text into segments:

```
ordinary text
special tokens
```

4. For special tokens:

- if allowed → emit token ID
- if disallowed → raise error

5. Encode ordinary segments using regex + BPE.

---

# 10. Byte-Pair Encoding (BPE)

This is the core tokenization algorithm.

### Input

```
bytes
```

### Output

```
list[int]
```

### Required table

```
mergeable_ranks: dict[bytes, int]
```

### Basic algorithm

1. Convert bytes into single-byte tokens.

```
[b'a', b'b', b'c']
```

2. Iteratively merge pairs with best rank.

3. Stop when no mergeable pairs remain.

4. Convert resulting byte pieces to token IDs.

---

### Simple implementation

Initial version:

- repeatedly scan adjacent pairs
- merge lowest rank pair
- continue until no valid merges

This approach prioritizes correctness.

---

### Optimized implementation

Later optimization may use:

- linked list representation
- priority queue for merges
- cached pair ranks

---

# 11. Decode Support

To implement `.decode(tokens)`:

1. Construct reverse mapping:

```
token_id → bytes
```

2. Concatenate bytes.

3. Decode UTF-8.

Recommended:

```
bytes.decode("utf-8", errors="replace")
```

Two functions should be provided:

```
decode_bytes(tokens)
decode(tokens)
```

---

# 12. Encoding Registry

A registry ensures encodings are loaded once.

```
_ENCODING_CACHE = {}
```

```
def get_encoding(name):
    if name in _ENCODING_CACHE:
        return _ENCODING_CACHE[name]

    encoding = load_encoding(name)
    _ENCODING_CACHE[name] = encoding
    return encoding
```

---

# 13. Exporting Encoding Data

A one-time export script must extract encoding data.

Required fields:

```
pat_str
mergeable_ranks
special_tokens
```

Export process:

1. Load encoding with real `tiktoken`
2. Extract fields
3. Serialize to JSON
4. Store in project repository

This export step may depend on external libraries but is **not required for runtime**.

---

# 14. Validation Strategy

A parity test suite must compare the pure implementation against `tiktoken`.

Test cases should include:

### ASCII text

```
plain English
punctuation
code
JSON
Markdown
```

### Unicode

```
accented Latin
emoji
CJK
combining characters
```

### Edge cases

```
empty string
very short strings
repeated whitespace
large text blocks
special token usage
```

For each test:

```
encode(text)
token count
decode(encode(text))
```

must match reference results.

---

# 15. Performance Considerations

A pure Python BPE implementation will be slower than the optimized upstream implementation.

Primary bottlenecks:

```
BPE merge loop
regex splitting
byte concatenation
```

### Recommended optimizations

Use caching for repeated substrings.

Example:

```
@lru_cache(maxsize=100000)
def bpe_encode_bytes(chunk: bytes):
```

Other optimizations:

- reuse byte objects
- avoid repeated concatenation
- minimize object allocations

---

# 16. Integration Example

Example replacement for a token counting script:

```python
import sys
from pure_tiktoken import get_encoding

def main():
    text = sys.stdin.read()
    enc = get_encoding("o200k_base")
    print(len(enc.encode(text)))

if __name__ == "__main__":
    main()
```

---

# 17. Technical Risks

## Regex Compatibility

The upstream tokenizer may depend on regex features not available in `re`.

Mitigation:

- validate pattern behavior early
- implement fallback scanning if necessary.

## Encoding Data Availability

`mergeable_ranks` and other tables must be extracted from the reference implementation.

Mitigation:

- perform one-time export
- freeze data in repository.

## Unicode Edge Cases

Differences in Unicode handling could introduce mismatches.

Mitigation:

- avoid normalization
- operate on raw UTF-8 bytes.

## Performance

Pure Python BPE is slower than optimized versions.

Mitigation:

- caching
- incremental optimization
- accept slower speed for token counting.

---

# 18. Recommended Implementation Order

1. Implement `Encoding` class skeleton.
2. Export `o200k_base` encoding data.
3. Implement JSON loader.
4. Implement basic BPE encoder.
5. Implement `encode(text)`.
6. Implement `decode`.
7. Build parity test harness.
8. Optimize performance.
9. Freeze encoding data.

---

# 19. Success Criteria

## Tier 1 — Practical Replacement

Supports:

```
get_encoding("o200k_base")
encode(text)
correct token counts
```

## Tier 2 — Strong Compatibility

Adds:

```
decode(tokens)
special token behavior
broad corpus parity
```

## Tier 3 — Full Compatibility

Adds:

```
identical edge-case handling
complete parity across fuzz corpus
```

---

# 20. Estimated Effort

Approximate engineering time:

```
Prototype implementation:        1 day
Correct implementation:          2–4 days
Parity testing and debugging:    3–7 days
Performance tuning:              2–5 days
```

Total expected effort:

```
1–2 weeks
```

---

# 21. Summary

Reimplementing the runtime behavior of:

```
tiktoken.get_encoding("o200k_base")
```

with only Python standard library dependencies is feasible.

The primary requirements are:

- exporting the encoding data once
- implementing regex pretokenization
- implementing BPE merging
- validating parity against the reference implementation

Once the encoding data is frozen, the tokenizer can operate entirely without external dependencies while maintaining compatibility with existing token counting workflows.

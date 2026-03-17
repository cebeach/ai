# BPE Tokenizer Tools Plan

| Field | Value |
|-------|-------|
| DocumentName | bpe_tokenizer_tools_plan |
| Category | design-spec |
| Revision | r3 |
| Fingerprint | 88170fe82bdf711232a65ad2f07961c7f33e7cc7ac89a32602165fbf2f0431a6 |
| Status | draft |
| Timestamp | 2026-03-17T16:45:11 |
| Authors | Chad Beach & ChatGPT-5 |

## Purpose

Define a deterministic plan for extracting a BPE tokenizer from the
`gpt-oss-20b` model artifact and providing a command‑line tokenizer
implementation with verification against `llama-server`.

## Overview

The project produces two primary tools and one verification harness.

1. Tokenizer Extractor
2. Tokenizer CLI
3. Verification Harness

The extractor produces a normalized JSON tokenizer artifact.
The CLI performs tokenization using that artifact.
The verification harness compares tokenizer behavior with `llama-server`.

## Architecture

Model Artifact → Extractor → JSON Tokenizer Artifact → Tokenizer CLI

Verification Harness → llama.cpp `llama-server`

Goals:

- reproducible tokenizer definitions
- deterministic tokenization behavior
- independent verification against server behavior

## Tool 1 — Tokenizer Extractor

### Purpose

Extract the BPE tokenizer definition from the `gpt-oss-20b` model artifact
and serialize it to a stable JSON tokenizer artifact.

The extractor performs no tokenization.

### Suggested Name

`extract_gpt_oss_bpe.py`

### Output Artifact

`gpt_oss_20b_bpe_tokenizer.json`

### CLI Interface

```
python extract_gpt_oss_bpe.py --model ~/models/openai_gpt-oss-20b.gguf   --output gpt_oss_20b_bpe_tokenizer.json
```

### Responsibilities

The extractor must:

- load tokenizer metadata from the model artifact
- verify tokenizer type is BPE
- extract vocabulary pieces
- extract merge ranks
- extract special tokens
- normalize tokenizer data to a stable JSON schema
- write the JSON artifact

The extractor must not perform tokenization.

## JSON Tokenizer Artifact Schema

Example structure:

```
{
  "format": "llama_bpe_tokenizer_v1",
  "source_model": "openai_gpt-oss-20b",
  "tokenizer_type": "BPE",
  "vocab_size": 201088,
  "pieces": ["!", "\""," #"],
  "merge_ranks": {
    "h e": 0,
    "he l": 1
  },
  "special_token_pieces": {
    "<|endoftext|>": 199999
  },
  "pretokenizer": {
    "name": "gpt_oss_default"
  },
  "byte_fallback": true
}
```

Design goals:

- deterministic
- minimal representation
- portable across implementations

## Extractor Implementation Phases

### Phase 1 — Loader

Extract tokenizer metadata:

- tokenizer type
- token pieces
- merge ranks
- special tokens
- tokenizer configuration

### Phase 2 — Validation

Fail if:

- tokenizer type is not BPE
- vocabulary missing
- merge ranks missing
- metadata malformed

### Phase 3 — Normalization

Convert model metadata to the stable JSON schema.

### Phase 4 — Artifact Writing

Write deterministic JSON:

- UTF‑8 encoding
- sorted keys
- stable indentation
- newline at end of file

## Tool 2 — Tokenizer CLI

### Purpose

Load the tokenizer artifact and tokenize input text.

Supported inputs:

- file path
- standard input

### Suggested Name

`bpe_tokenize.py`

### CLI Examples

Tokenize file:

```
python bpe_tokenize.py --tokenizer gpt_oss_20b_bpe_tokenizer.json --file input.txt
```

Tokenize stdin:

```
cat input.txt | python bpe_tokenize.py --tokenizer gpt_oss_20b_bpe_tokenizer.json
```

### CLI Input Rules

- if `--file` provided read the file
- else if stdin is not a TTY read stdin
- else exit with an error

### Output Modes

Supported options:

- `--count-only`
- `--ids-only`
- `--json`

Default output format:

```
token_count: 123
token_ids: 12 45 998 1024
```

JSON output example:

```
{
  "token_count": 123,
  "token_ids": [12,45,998,1024]
}
```

## Tokenizer Implementation

### Phase 1 — Artifact Loader

Load JSON artifact and validate schema.

### Phase 2 — In‑Memory Structures

Construct:

- `id_to_piece`
- `piece_to_id`
- `merge_rank[(left,right)]`
- special token tables

### Phase 3 — Pretokenization

Implement the pretokenization behavior defined in the artifact.

### Phase 4 — BPE Merge Engine

Algorithm:

1. pretokenize input
2. convert chunk to initial symbols
3. repeatedly merge lowest rank adjacent pairs
4. produce final token pieces
5. map pieces to token IDs

## Verification Harness

A verification tool compares tokenizer CLI results with
`llama-server` results.

Suggested name:

`verify_tokenizer_against_llama_server.py`

### Verification Flow

Start server:

```
./llama-server -m openai_gpt-oss-20b.gguf
```

Send tokenization request:

```
POST /v1/tokenize
{ "text": "example input" }
```

Example response:

```
{ "tokens": [12,345,98], "count": 3 }
```

### Validation

Verify:

- token IDs identical
- token counts identical

## Differential Test Corpus

Test inputs must include:

- natural language sentences
- code snippets
- punctuation heavy text
- whitespace heavy text
- Unicode characters
- empty input
- long repeated strings

## Regression Testing

Store test fixtures:

```
tests/corpus/
  english.txt
  unicode.txt
  whitespace.txt
  code_samples.txt
```

Automated test example:

```
python verify_tokenizer_against_llama_server.py   --tokenizer gpt_oss_20b_bpe_tokenizer.json   --server http://localhost:8080
```

## Repository Layout

```
tools/
  extract_gpt_oss_bpe.py
  bpe_tokenize.py
  verify_tokenizer_against_llama_server.py

src/llama_bpe/
  artifact_schema.py
  extractor.py
  artifact_loader.py
  vocab.py
  pretokenizer.py
  bpe.py
  llama_server_client.py

tests/
  test_extractor.py
  test_tokenize_file.py
  test_tokenize_stdin.py
  test_llama_server_verification.py
```

## Implementation Milestones

### Milestone 1

Extractor implemented producing:

`gpt_oss_20b_bpe_tokenizer.json`

### Milestone 2

Tokenizer CLI implemented supporting:

- file input
- stdin input
- token IDs
- token counts

### Milestone 3

Document server token counting behavior.

### Milestone 4

Verification harness implemented.

### Milestone 5

Regression tests implemented.

## Minimal Deliverable

1. Extract BPE tokenizer from `gpt-oss-20b`
2. Produce JSON tokenizer artifact
3. Tokenize file and stdin using CLI
4. Verify results against `llama-server`

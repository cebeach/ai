"""Extract and pretty-print architecture metadata from a GGUF model file.

Usage:
    python gguf_model_info.py <model.gguf>

Requires:
    pip install gguf prettytable
"""

import sys
from pathlib import Path


def get_field_value(fields: dict, key: str):
    """Extract a scalar value from a GGUFReader field by key name."""
    field = fields.get(key)
    if field is None:
        return None
    try:
        val = field.parts[-1][0]
        if isinstance(val, (bytes, bytearray)):
            return val.decode("utf-8")
        return val
    except (IndexError, AttributeError):
        return None


def get_string_field(fields: dict, key: str) -> str | None:
    """Extract a string field, handling the gguf byte-array encoding."""
    field = fields.get(key)
    if field is None:
        return None
    try:
        for part in reversed(field.parts):
            try:
                val = part.tobytes().decode("utf-8").rstrip("\x00")
                if val:
                    return val
            except Exception:
                continue
    except Exception:
        pass
    return None


def fmt_int(val) -> str:
    if val is None:
        return "—"
    return f"{int(val):,}"


def fmt_float(val, decimals: int = 2) -> str:
    if val is None:
        return "—"
    return f"{float(val):.{decimals}f}"


def fmt_str(val) -> str:
    return str(val) if val is not None else "—"


def make_table(title: str, rows: list[tuple]) -> str:
    """Build a titled PrettyTable from (property, value) or (property, value, note) tuples.
    Rows where property is None act as blank-line dividers.
    Rows where value is None are skipped entirely.
    """
    from prettytable import PrettyTable, TableStyle

    has_notes = any(len(r) == 3 and r[2] for r in rows if r[0] is not None)

    if has_notes:
        t = PrettyTable(field_names=["Property", "Value", "Note"])
        t.align["Note"] = "l"
    else:
        t = PrettyTable(field_names=["Property", "Value"])

    t.align["Property"] = "l"
    t.align["Value"] = "l"
    t.set_style(TableStyle.SINGLE_BORDER)

    for row in rows:
        if row[0] is None:
            # Blank divider row
            t.add_row(["", "", ""] if has_notes else ["", ""])
            continue
        if row[1] is None:
            continue
        if has_notes:
            t.add_row([row[0], row[1], row[2] if len(row) == 3 else ""])
        else:
            t.add_row([row[0], row[1]])

    # Inject the section title into the top border
    lines = t.get_string().splitlines()
    title_str = f" {title} "
    border = lines[0]
    if len(title_str) < len(border) - 4:
        lines[0] = border[:2] + title_str + border[2 + len(title_str) :]

    return "\n".join(lines)


def report(model_path: Path) -> None:
    try:
        from gguf import GGUFReader, Keys, LlamaFileType
    except ImportError:
        print("Error: gguf not installed. Run: pip install gguf", file=sys.stderr)
        sys.exit(1)
    try:
        from prettytable import PrettyTable  # noqa: F401
    except ImportError:
        print("Error: prettytable not installed. Run: pip install prettytable", file=sys.stderr)
        sys.exit(1)

    print(f"\n  Model : {model_path}")
    print(f"  Size  : {model_path.stat().st_size / (1024**3):.2f} GiB")

    reader = GGUFReader(str(model_path), mode="r")
    fields = reader.fields

    arch = get_string_field(fields, Keys.General.ARCHITECTURE)
    if arch is None:
        print("Error: could not read general.architecture.", file=sys.stderr)
        sys.exit(1)

    def k(template: str) -> str:
        return template.format(arch=arch)

    # ------------------------------------------------------------------ #
    # General                                                              #
    # ------------------------------------------------------------------ #
    name = get_string_field(fields, Keys.General.NAME)
    size_label = get_string_field(fields, Keys.General.SIZE_LABEL)
    file_type = get_field_value(fields, Keys.General.FILE_TYPE)
    license_ = get_string_field(fields, Keys.General.LICENSE)

    file_type_str = "—"
    if file_type is not None:
        try:
            file_type_str = LlamaFileType(int(file_type)).name
        except (ValueError, KeyError):
            file_type_str = str(int(file_type))

    print()
    print(
        make_table(
            "GENERAL",
            [
                ("Name", fmt_str(name)),
                ("Architecture", fmt_str(arch)),
                ("Size label", fmt_str(size_label)),
                ("File type", file_type_str),
                ("License", fmt_str(license_)),
            ],
        )
    )

    # ------------------------------------------------------------------ #
    # Context & dimensions                                                 #
    # ------------------------------------------------------------------ #
    ctx_len = get_field_value(fields, k(Keys.LLM.CONTEXT_LENGTH))
    n_layers = get_field_value(fields, k(Keys.LLM.BLOCK_COUNT))
    n_embd = get_field_value(fields, k(Keys.LLM.EMBEDDING_LENGTH))
    n_ff = get_field_value(fields, k(Keys.LLM.FEED_FORWARD_LENGTH))
    vocab_size = get_field_value(fields, k(Keys.LLM.VOCAB_SIZE))

    print()
    print(
        make_table(
            "CONTEXT & DIMENSIONS",
            [
                ("Max context length", fmt_int(ctx_len), "tokens"),
                ("Layers (block count)", fmt_int(n_layers)),
                ("Embedding dimension", fmt_int(n_embd)),
                ("Feed-forward length", fmt_int(n_ff)),
                ("Vocabulary size", fmt_int(vocab_size)),
            ],
        )
    )

    # ------------------------------------------------------------------ #
    # Attention                                                            #
    # ------------------------------------------------------------------ #
    n_head = get_field_value(fields, k(Keys.Attention.HEAD_COUNT))
    n_head_kv = get_field_value(fields, k(Keys.Attention.HEAD_COUNT_KV))
    key_len = get_field_value(fields, k(Keys.Attention.KEY_LENGTH))
    val_len = get_field_value(fields, k(Keys.Attention.VALUE_LENGTH))
    swa_window = get_field_value(fields, k(Keys.Attention.SLIDING_WINDOW))
    swa_pattern = get_field_value(fields, k("{arch}.attention.sliding_window_pattern"))
    rms_eps = get_field_value(fields, k(Keys.Attention.LAYERNORM_RMS_EPS))

    gqa = fmt_int(int(n_head) // int(n_head_kv)) if n_head and n_head_kv else "—"

    attn_rows: list[tuple] = [
        ("Q heads", fmt_int(n_head)),
        ("KV heads", fmt_int(n_head_kv)),
        ("GQA ratio (Q / KV)", gqa),
        ("Head dimension (K)", fmt_int(key_len)),
        ("Head dimension (V)", fmt_int(val_len)),
    ]
    if swa_window is not None:
        attn_rows += [
            (None, None),
            ("Sliding window size", fmt_int(swa_window), "tokens per SWA layer"),
        ]
        if swa_pattern is not None:
            attn_rows.append(("SWA layer pattern", fmt_str(swa_pattern)))
    if rms_eps is not None:
        attn_rows += [(None, None), ("RMS norm epsilon", fmt_float(rms_eps, 10))]

    print()
    print(make_table("ATTENTION", attn_rows))

    # ------------------------------------------------------------------ #
    # MoE experts                                                          #
    # ------------------------------------------------------------------ #
    n_experts = get_field_value(fields, k(Keys.LLM.EXPERT_COUNT))
    n_experts_used = get_field_value(fields, k(Keys.LLM.EXPERT_USED_COUNT))
    n_expert_groups = get_field_value(fields, k("{arch}.expert_group_count"))
    expert_ff_len = get_field_value(fields, k(Keys.LLM.EXPERT_FEED_FORWARD_LENGTH))
    shared_experts = get_field_value(fields, k(Keys.LLM.EXPERT_SHARED_COUNT))

    if n_experts is not None:
        pct = f"{int(n_experts_used) / int(n_experts) * 100:.1f}%" if n_experts_used else "—"
        moe_rows: list[tuple] = [
            ("Total experts", fmt_int(n_experts)),
            ("Active experts / token", fmt_int(n_experts_used)),
            ("Expert utilization", pct),
        ]
        if n_expert_groups is not None:
            moe_rows.append(("Expert groups", fmt_int(n_expert_groups)))
        if shared_experts is not None:
            moe_rows.append(("Shared experts", fmt_int(shared_experts)))
        if expert_ff_len is not None:
            moe_rows.append(("Expert FF length", fmt_int(expert_ff_len)))
        print()
        print(make_table("MIXTURE OF EXPERTS", moe_rows))

    # ------------------------------------------------------------------ #
    # RoPE                                                                 #
    # ------------------------------------------------------------------ #
    rope_type = get_string_field(fields, k(Keys.Rope.SCALING_TYPE))
    rope_factor = get_field_value(fields, k(Keys.Rope.SCALING_FACTOR))
    rope_orig_ctx = get_field_value(fields, k(Keys.Rope.SCALING_ORIG_CTX_LEN))
    rope_freq_base = get_field_value(fields, k(Keys.Rope.FREQ_BASE))
    rope_dim = get_field_value(fields, k(Keys.Rope.DIMENSION_COUNT))

    rope_rows: list[tuple] = [
        ("Frequency base", fmt_float(rope_freq_base, 1) if rope_freq_base else "—"),
        ("RoPE dimensions", fmt_int(rope_dim)),
    ]
    if rope_type is not None:
        rope_rows += [
            (None, None),
            ("Scaling type", fmt_str(rope_type)),
            ("Scaling factor", fmt_float(rope_factor) if rope_factor else "—"),
            ("Original context", fmt_int(rope_orig_ctx) if rope_orig_ctx else "—", "tokens (pre-scaling)"),
        ]
        if ctx_len and rope_orig_ctx:
            rope_rows.append(("Context extension", f"{int(ctx_len) / int(rope_orig_ctx):.1f}×"))

    print()
    print(make_table("ROPE POSITIONAL ENCODING", rope_rows))

    # ------------------------------------------------------------------ #
    # Tokenizer                                                            #
    # ------------------------------------------------------------------ #
    tok_model = get_string_field(fields, Keys.Tokenizer.MODEL)
    tok_pre = get_string_field(fields, Keys.Tokenizer.PRE)
    bos_id = get_field_value(fields, Keys.Tokenizer.BOS_ID)
    eos_id = get_field_value(fields, Keys.Tokenizer.EOS_ID)
    pad_id = get_field_value(fields, Keys.Tokenizer.PAD_ID)

    print()
    print(
        make_table(
            "TOKENIZER",
            [
                ("Model", fmt_str(tok_model)),
                ("Pre", fmt_str(tok_pre)),
                ("BOS token ID", fmt_int(bos_id)),
                ("EOS token ID", fmt_int(eos_id)),
                ("PAD token ID", fmt_int(pad_id)),
            ],
        )
    )

    # ------------------------------------------------------------------ #
    # Tensors                                                              #
    # ------------------------------------------------------------------ #
    quant_counts: dict[str, int] = {}
    quant_params: dict[str, int] = {}
    total_params = 0

    for tensor in reader.tensors:
        qt = tensor.tensor_type.name
        n = tensor.n_elements
        quant_counts[qt] = quant_counts.get(qt, 0) + 1
        quant_params[qt] = quant_params.get(qt, 0) + n
        total_params += n

    tensor_rows: list[tuple] = [
        ("Total tensors", fmt_int(len(reader.tensors))),
        ("Total parameters", fmt_int(total_params)),
    ]
    if quant_counts:
        tensor_rows.append((None, None))
        # Sort by parameter count descending
        for qt, params in sorted(quant_params.items(), key=lambda x: -x[1]):
            count = quant_counts[qt]
            pct = params / total_params * 100
            tensor_rows.append(
                (
                    f"  {qt}",
                    fmt_int(count),
                    f"{fmt_int(params)} params  ({pct:.2f}%)",
                )
            )

    print()
    print(make_table("TENSORS", tensor_rows))
    print()


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <model.gguf>", file=sys.stderr)
        return 1

    model_path = Path(sys.argv[1])
    if not model_path.exists():
        print(f"Error: file not found: {model_path}", file=sys.stderr)
        return 1

    if model_path.suffix != ".gguf":
        print(f"Warning: file does not have .gguf extension: {model_path}", file=sys.stderr)

    report(model_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

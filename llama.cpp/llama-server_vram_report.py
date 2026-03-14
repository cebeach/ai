#!/usr/bin/env python3
"""Parse a llama-server log file and pretty-print a VRAM metrics report.

Usage:
    python llama_server_vram_report.py <log_file>
    python llama_server_vram_report.py /tmp/chad/llama-server_*.txt
"""

import re
import sys
from pathlib import Path


def parse_log(log_path: Path) -> dict:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    metrics = {}

    # Model file size and BPW
    m = re.search(r"file size\s+=\s+([\d.]+)\s+GiB\s+\(([\d.]+)\s+BPW\)", text)
    if m:
        metrics["model_file_gib"] = float(m.group(1))
        metrics["model_bpw"] = float(m.group(2))

    # Free VRAM at startup (first occurrence, before model load)
    m = re.search(r"(\d+)\s+MiB free", text)
    if m:
        metrics["vram_free_at_startup_mib"] = int(m.group(1))

    # Total VRAM on device
    m = re.search(r"\|\s*-\s*CUDA0[^|]+\|\s*(\d+)\s*=", text)
    if m:
        metrics["vram_total_mib"] = int(m.group(1))

    # Full memory breakdown line
    m = re.search(
        r"CUDA0[^|]+\|\s*(\d+)\s*=\s*(\d+)\s*\+\s*\((\d+)\s*=\s*(\d+)\s*\+\s*(\d+)\s*\+\s*(\d+)\)",
        text,
    )
    if m:
        metrics["vram_total_mib"] = int(m.group(1))
        metrics["vram_free_at_startup_mib"] = int(m.group(2))
        metrics["vram_used_total_mib"] = int(m.group(3))
        metrics["vram_model_weights_mib"] = int(m.group(4))
        metrics["vram_kv_cache_mib"] = int(m.group(5))
        metrics["vram_compute_buffer_mib"] = int(m.group(6))

    # Free VRAM after load (from fit summary)
    m = re.search(r"will leave (\d+) >= \d+ MiB of free device memory", text)
    if m:
        metrics["vram_free_after_load_mib"] = int(m.group(1))

    # n_parallel (slot count) — three log formats depending on invocation:
    # 1. explicit --parallel N: "initializing slots, n_slots = 4"
    # 2. auto-detection:        "n_parallel is set to auto, using n_parallel = 4"
    # 3. fallback:              bare "n_parallel = N" anywhere in log
    m = re.search(r"initializing slots,\s+n_slots\s*=\s*(\d+)", text)
    if m:
        metrics["n_slots"] = int(m.group(1))
    else:
        m = re.search(r"n_parallel(?:\s+is set to auto,)?\s+using\s+n_parallel\s*=\s*(\d+)", text)
        if m:
            metrics["n_slots"] = int(m.group(1))
        else:
            m = re.search(r"n_parallel\s*=\s*(\d+)", text)
            if m:
                metrics["n_slots"] = int(m.group(1))

    # Per-slot context size (may be capped below --ctx-size by model training context)
    m = re.search(r"new slot, n_ctx\s*=\s*(\d+)", text)
    if m:
        metrics["n_ctx_per_slot"] = int(m.group(1))

    # kv_unified
    metrics["kv_unified"] = bool(re.search(r"kv_unified\s*=\s*true", text))

    # Non-SWA KV cache — summary line follows the iswa creation line
    # Log format: llama_kv_cache: size = 1632.00 MiB (131072 cells,  12 layers,  4/1 seqs)
    # Preceded by: llama_kv_cache_iswa: creating non-SWA KV cache
    m = re.search(
        r"creating non-SWA KV cache.*?\n"
        r"(?:.*?\n)*?.*?llama_kv_cache: size =\s+([\d.]+)\s+MiB\s+\(\s*(\d+)\s+cells,\s*(\d+)\s+layers",
        text,
    )
    if m:
        metrics["kv_nonswa_total_mib"] = float(m.group(1))
        metrics["kv_nonswa_cells"] = int(m.group(2))
        metrics["kv_nonswa_layers"] = int(m.group(3))

    # SWA KV cache
    m = re.search(
        r"creating\s+SWA KV cache.*?\n"
        r"(?:.*?\n)*?.*?llama_kv_cache: size =\s+([\d.]+)\s+MiB\s+\(\s*(\d+)\s+cells,\s*(\d+)\s+layers",
        text,
    )
    if m:
        metrics["kv_swa_total_mib"] = float(m.group(1))
        metrics["kv_swa_cells"] = int(m.group(2))
        metrics["kv_swa_layers"] = int(m.group(3))

    # KV quantization — from the KV cache size summary line
    m = re.search(r"llama_kv_cache: size =.*?K \((\w+)\).*?V \((\w+)\)", text)
    if m:
        metrics["kv_quant_k"] = m.group(1)
        metrics["kv_quant_v"] = m.group(2)

    # Context size
    m = re.search(r"context_length\s+u32\s+=\s+(\d+)", text)
    if m:
        metrics["ctx_size"] = int(m.group(1))

    # Architecture
    m = re.search(r"general\.architecture\s+str\s+=\s+(\S+)", text)
    if m:
        metrics["architecture"] = m.group(1)

    # Model name
    m = re.search(r"general\.name\s+str\s+=\s+(.+)", text)
    if m:
        metrics["model_name"] = m.group(1).strip()

    # File type (e.g. "MXFP4 MoE")
    m = re.search(r"print_info: file type\s+=\s+(.+)", text)
    if m:
        metrics["file_type"] = m.group(1).strip()

    # Total parameters
    m = re.search(r"print_info: model params\s+=\s+([\d.]+\s+\S+)", text)
    if m:
        metrics["model_params"] = m.group(1).strip()

    # Layers, heads
    m = re.search(r"print_info: n_layer\s+=\s+(\d+)", text)
    if m:
        metrics["n_layer"] = int(m.group(1))

    m = re.search(r"print_info: n_head\s+=\s+(\d+)", text)
    if m:
        metrics["n_head"] = int(m.group(1))

    m = re.search(r"print_info: n_head_kv\s+=\s+(\d+)", text)
    if m:
        metrics["n_head_kv"] = int(m.group(1))

    m = re.search(r"print_info: n_embd_head_k\s+=\s+(\d+)", text)
    if m:
        metrics["n_embd_head_k"] = int(m.group(1))

    m = re.search(r"print_info: n_embd_head_v\s+=\s+(\d+)", text)
    if m:
        metrics["n_embd_head_v"] = int(m.group(1))

    # Embedding length
    m = re.search(r"embedding_length\s+u32\s+=\s+(\d+)", text)
    if m:
        metrics["n_embd"] = int(m.group(1))

    # MoE experts
    m = re.search(r"print_info: n_expert\s+=\s+(\d+)", text)
    if m:
        metrics["n_expert"] = int(m.group(1))

    m = re.search(r"print_info: n_expert_used\s+=\s+(\d+)", text)
    if m:
        metrics["n_expert_used"] = int(m.group(1))

    # Rope scaling
    m = re.search(r"print_info: rope scaling\s+=\s+(\S+)", text)
    if m:
        metrics["rope_scaling"] = m.group(1).strip()

    m = re.search(r"rope\.scaling\.factor\s+f32\s+=\s+([\d.]+)", text)
    if m:
        metrics["rope_scaling_factor"] = float(m.group(1))

    m = re.search(r"print_info: n_ctx_orig_yarn\s+=\s+(\d+)", text)
    if m:
        metrics["rope_orig_ctx"] = int(m.group(1))

    # SWA window size (from kv metadata)
    m = re.search(r"attention\.sliding_window\s+u32\s+=\s+(\d+)", text)
    if m:
        metrics["swa_window"] = int(m.group(1))

    # SWA/non-SWA layer split from load_tensors assignments.
    # Each line: "load_tensors: layer   N assigned to device CUDA0, is_swa = 0|1"
    # Layer N == n_layer is the output/embedding, not a transformer block — exclude it.
    # The log contains two passes (fit probe + actual load); deduplicate by layer number.
    n_layer = metrics.get("n_layer", 9999)
    all_assignments = re.findall(
        r"load_tensors: layer\s+(\d+)\s+assigned[^\n]*is_swa\s*=\s*([01])",
        text,
    )
    seen: dict[int, str] = {}
    for layer_str, swa in all_assignments:
        layer = int(layer_str)
        if layer < n_layer:
            seen[layer] = swa  # last write wins; both passes should agree
    if seen:
        metrics["layers_swa"] = sum(1 for swa in seen.values() if swa == "1")
        metrics["layers_nonswa"] = sum(1 for swa in seen.values() if swa == "0")

    # Compute buffer (CUDA)
    m = re.search(r"CUDA0\s+compute buffer size\s+=\s+([\d.]+)\s+MiB", text)
    if m:
        metrics["compute_buffer_cuda_mib"] = float(m.group(1))

    # Compute buffer (Host)
    m = re.search(r"CUDA_Host\s+compute buffer size\s+=\s+([\d.]+)\s+MiB", text)
    if m:
        metrics["compute_buffer_host_mib"] = float(m.group(1))

    # CPU mapped model buffer
    m = re.search(r"CPU_Mapped model buffer size\s+=\s+([\d.]+)\s+MiB", text)
    if m:
        metrics["model_cpu_mapped_mib"] = float(m.group(1))

    # CUDA model buffer — take the last non-zero occurrence (first is a fit probe)
    cuda_bufs = re.findall(r"CUDA0 model buffer size\s+=\s+([\d.]+)\s+MiB", text)
    nonzero = [float(x) for x in cuda_bufs if float(x) > 0]
    if nonzero:
        metrics["model_cuda_mib"] = nonzero[-1]

    return metrics


def mib_to_gib(mib: float) -> str:
    return f"{mib / 1024:.2f} GiB"


def row(label: str, value: str, note: str = "") -> None:
    note_str = f"  # {note}" if note else ""
    print(f"  {label:<40} {value:<16}{note_str}")


def separator(char: str = "-", width: int = 72) -> None:
    print("  " + char * width)


def header(title: str, width: int = 72) -> None:
    print()
    print("  " + "=" * width)
    print(f"  {title}")
    print("  " + "=" * width)


def report(metrics: dict, log_path: Path) -> None:
    n_slots = metrics.get("n_slots", 1)
    kv_nonswa = metrics.get("kv_nonswa_total_mib", 0.0)
    kv_swa = metrics.get("kv_swa_total_mib", 0.0)
    kv_total = kv_nonswa + kv_swa
    kv_per_slot = kv_total / n_slots if n_slots else 0.0
    kv_nonswa_per_slot = kv_nonswa / n_slots if n_slots else 0.0
    kv_swa_per_slot = kv_swa / n_slots if n_slots else 0.0

    vram_total = metrics.get("vram_total_mib", 0)
    vram_free_after = metrics.get("vram_free_after_load_mib", 0)
    llama_safety_margin = 1024  # MiB — llama.cpp's built-in minimum headroom

    usable_for_slots = max(0, vram_free_after - llama_safety_margin)
    extra_slots = int(usable_for_slots / kv_per_slot) if kv_per_slot > 0 else 0
    max_slots = n_slots + extra_slots

    print()
    print(f"  Log file : {log_path}")

    header("MODEL")
    row("Name", metrics.get("model_name", "unknown"))
    row("Architecture", metrics.get("architecture", "unknown"))
    row("File type", metrics.get("file_type", "unknown"))
    row("File size", f"{metrics.get('model_file_gib', 0):.2f} GiB")
    row("Quantization", f"{metrics.get('model_bpw', 0):.2f} BPW")
    row("Total parameters", metrics.get("model_params", "unknown"))
    row("Context length", f"{metrics.get('ctx_size', 0):,} tokens")
    row("KV quantization (K)", metrics.get("kv_quant_k", "unknown"))
    row("KV quantization (V)", metrics.get("kv_quant_v", "unknown"))

    header("MODEL ARCHITECTURE")
    row("Layers (total)", str(metrics.get("n_layer", "unknown")))
    if "layers_nonswa" in metrics and "layers_swa" in metrics:
        row("  Full-attention layers", str(metrics["layers_nonswa"]))
        row("  SWA layers", str(metrics["layers_swa"]))
        if "swa_window" in metrics:
            row("  SWA window size", f"{metrics['swa_window']:,} tokens")
    row("Embedding dimension", str(metrics.get("n_embd", "unknown")))
    row("Attention heads (Q)", str(metrics.get("n_head", "unknown")))
    row("Attention heads (KV)", str(metrics.get("n_head_kv", "unknown")))
    row("Head dimension (K)", str(metrics.get("n_embd_head_k", "unknown")))
    row("Head dimension (V)", str(metrics.get("n_embd_head_v", "unknown")))
    if "n_expert" in metrics:
        separator()
        row("Experts (total)", str(metrics["n_expert"]))
        row("Experts (active per token)", str(metrics.get("n_expert_used", "unknown")))
        if metrics.get("n_expert") and metrics.get("n_expert_used"):
            pct = metrics["n_expert_used"] / metrics["n_expert"] * 100
            row("Expert utilization", f"{pct:.1f}%")
    if "rope_scaling" in metrics:
        separator()
        row("RoPE scaling", metrics["rope_scaling"])
        if "rope_scaling_factor" in metrics:
            row("RoPE scaling factor", str(metrics["rope_scaling_factor"]))
        if "rope_orig_ctx" in metrics:
            row("RoPE original context", f"{metrics['rope_orig_ctx']:,} tokens")

    header("VRAM ALLOCATION  (CUDA0)")
    row("Total VRAM", mib_to_gib(vram_total), f"{vram_total:,} MiB")
    row("Free at startup", mib_to_gib(metrics.get("vram_free_at_startup_mib", 0)),
        f"{metrics.get('vram_free_at_startup_mib', 0):,} MiB")
    separator()
    row("  Model weights (CUDA)", mib_to_gib(metrics.get("model_cuda_mib", 0)),
        f"{metrics.get('model_cuda_mib', 0):,.0f} MiB")
    row("  Model weights (CPU mapped)", mib_to_gib(metrics.get("model_cpu_mapped_mib", 0)),
        f"{metrics.get('model_cpu_mapped_mib', 0):,.0f} MiB")
    row("  KV cache (non-SWA)", mib_to_gib(kv_nonswa), f"{kv_nonswa:,.2f} MiB")
    row("  KV cache (SWA)", mib_to_gib(kv_swa), f"{kv_swa:,.2f} MiB")
    row("  Compute buffer (CUDA)", mib_to_gib(metrics.get("compute_buffer_cuda_mib", 0)),
        f"{metrics.get('compute_buffer_cuda_mib', 0):,.2f} MiB")
    separator()
    used = metrics.get("vram_used_total_mib", 0)
    row("Total used", mib_to_gib(used), f"{used:,} MiB")
    row("Free after load", mib_to_gib(vram_free_after), f"{vram_free_after:,} MiB")

    header("KV CACHE DETAIL")
    row("Slots (n_parallel)", str(n_slots))
    row("KV unified", str(metrics.get("kv_unified", False)))
    if "n_ctx_per_slot" in metrics:
        ctx_per_slot = metrics["n_ctx_per_slot"]
        ctx_total = metrics.get("kv_nonswa_cells", 0)
        note = ""
        if ctx_total and n_slots and ctx_per_slot < ctx_total // n_slots:
            note = "capped at model training context"
        row("Context per slot", f"{ctx_per_slot:,} tokens", note)
    row("Non-SWA layers", str(metrics.get("kv_nonswa_layers", 0)))
    row("Non-SWA cells (context tokens)", f"{metrics.get('kv_nonswa_cells', 0):,}")
    row("SWA layers", str(metrics.get("kv_swa_layers", 0)))
    row("SWA cells (window tokens)", f"{metrics.get('kv_swa_cells', 0):,}")
    separator()
    row("KV cache per slot (non-SWA)", f"{kv_nonswa_per_slot:.2f} MiB")
    row("KV cache per slot (SWA)", f"{kv_swa_per_slot:.2f} MiB")
    row("KV cache per slot (total)", f"{kv_per_slot:.2f} MiB")

    header("SLOT CAPACITY ANALYSIS")
    row("Current slots", str(n_slots))
    row("Free VRAM after load", mib_to_gib(vram_free_after), f"{vram_free_after:,} MiB")
    row("llama.cpp safety margin", mib_to_gib(llama_safety_margin), f"{llama_safety_margin:,} MiB")
    row("Usable for additional slots", mib_to_gib(usable_for_slots), f"{usable_for_slots:,} MiB")
    row("KV cost per slot", f"{kv_per_slot:.2f} MiB")
    separator()
    row("Additional slots possible", str(extra_slots))
    row("Maximum slots (estimated)", str(max_slots),
        "keeping llama.cpp safety margin")

    print()
    print("  " + "=" * 72)
    print()


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <log_file>", file=sys.stderr)
        return 1

    log_path = Path(sys.argv[1])
    if not log_path.exists():
        print(f"Error: file not found: {log_path}", file=sys.stderr)
        return 1

    metrics = parse_log(log_path)
    report(metrics, log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

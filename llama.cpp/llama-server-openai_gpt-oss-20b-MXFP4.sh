#!/bin/bash

# Welcome to the gpt-oss series, OpenAI’s open-weight models designed for powerful reasoning, agentic tasks, and versatile developer use cases.
#
# https://openai.com/index/introducing-gpt-oss
# GPT-OSS-20B is a Mixture-of-Experts model:
#    20.9B total parameters
#    ~3.6B active per token
#    24 transformer layers
#    Hybrid attention (global + sliding window)
#    Context length up to 128K
#
# OpenAI
# https://huggingface.co/openai/gpt-oss-120b
# https://openai.com/index/introducing-gpt-oss
# https://arxiv.org/pdf/2508.10925
# https://github.com/openai/gpt-oss
# https://github.com/openai/gpt-oss/blob/main/awesome-gpt-oss.md
# https://developers.openai.com/cookbook/articles/openai-harmony
#
# Huggingface (GGUF)
# https://huggingface.co/openai/gpt-oss-120b
#
# You can adjust the reasoning level that suits your task across three levels:
#    Low: Fast responses for general dialogue.
#    Medium: Balanced speed and detail.
#    High: Deep and detailed analysis.
#
# These are set in the system prompt; using OpenCode, these can be set in an agent's prompt; e.g.
# Reasoning: medium
#
#
# Tool use
# The gpt-oss models are excellent for:
#     Web browsing (using built-in browsing tools)
#     Function calling with defined schemas
#     Agentic operations like browser tasks

model=openai_gpt-oss-20b-MXFP4
CTX_LEN=131072
SLOTS=4

timestamp=$(date '+%Y%m%d_%H%M%S')

# Log files and llama-slots are rooted under $TMP:
TMP=/tmp/llama-server
mkdir -p ${TMP}/log
mkdir -p ${TMP}/slots

HOSTNAME=$(hostname -f 2>/dev/null || hostname)

log() { echo "[${HOSTNAME}] $*"; }

LOG_FILE=${TMP}/log/llama-server_${model}_${timestamp}.txt

log "log file ${LOG_FILE}"

log "=== Server started: ${timestamp} ===" > ${LOG_FILE}

# Note: --log-timestamps doesn't work unless --log-prefix is passed
# ChatGPT helped me with this and also referenced: https://github.com/ggml-org/llama.cpp/discussions/11924

# Claude helped me analyze the source code to suss out the details on parallel slot usage.
# When --parallel is not specified, --parallel defaults to 4 with unified KV cache.
# When --parallel is specified, KV cache is not unified across slots unless --kv-unified is passed as well.
#
# --kv-unified shared context pool
CTX_SIZE=$(python3 -c "print(${SLOTS} * ${CTX_LEN})")

log "${model} supported context length = ${CTX_LEN} tokens" >> ${LOG_FILE}
log "Using ${SLOTS} slots (capable of supporting ${SLOTS} concurrent conversations)"
log "Using --ctx-size ${CTX_SIZE} tokens shared context pool" >> ${LOG_FILE}
log "Effective context length of ${CTX_LEN} tokens per slot"
log "Running $(which llama-server)" >> ${LOG_FILE}
log "llama-server --version: $(llama-server --version 2>&1 | tr -s ' \n' ' ' | xargs)" >> ${LOG_FILE}

llama-server \
  --model /home/chad/gguf/${model}.gguf \
  --n-gpu-layers 99 \
  --ctx-size ${CTX_SIZE} \
  --flash-attn on \
  --jinja \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --batch-size 4096 \
  --ubatch-size 1024 \
  --kv-unified \
  --parallel ${SLOTS} \
  --slot-save-path ${TMP}/slots \
  --log-prefix \
  --log-verbose \
  --log-timestamps \
  --port 8001 \
  --host 127.0.0.1 2>&1 | tee -a ${LOG_FILE}


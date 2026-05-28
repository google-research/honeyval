#!/bin/bash

N_SAMPLES=5
MAX_WORKERS=80
HONEYPOT_REASONING_EFFORT="low"
HONEYPOT_INSTRUCTION="none"
PENTEST_MODEL="vertex_ai/gemini-3-flash-preview"
HONEYPOT_MODEL="vertex_ai/gemini-3-flash-preview"
PENTESTING_PROMPT="exploit-detect"
HONEYPOT_TYPE="rule-based"
EXPERIMENT_NAME="rule-based-honeypots"
PENTEST_REASONING_EFFORT="high"

python src/main.py \
    --mode "run" \
    --meta_experiment_type "$EXPERIMENT_NAME" \
    --pentest_model "$PENTEST_MODEL" \
    --honeypot_model "$HONEYPOT_MODEL" \
    --honeypot_additional_instructions "$HONEYPOT_INSTRUCTION" \
    --n_samples "$N_SAMPLES" \
    --pentesting_prompt "$PENTESTING_PROMPT" \
    --honeypot_reasoning_effort "$HONEYPOT_REASONING_EFFORT" \
    --max_workers "$MAX_WORKERS" \
    --honeypot_type "$HONEYPOT_TYPE" \
    --pentest_timeout 3600 \
    --pentest_reasoning_effort "$PENTEST_REASONING_EFFORT" \
    --benchmark_tasks "static-vs-http-app"

python src/main.py \
    --mode "evaluate" \
    --meta_experiment_type "$EXPERIMENT_NAME" \
    --pentest_model "$PENTEST_MODEL" \
    --honeypot_model "$HONEYPOT_MODEL" \
    --honeypot_additional_instructions "$HONEYPOT_INSTRUCTION" \
    --n_samples "$N_SAMPLES" \
    --pentesting_prompt "$PENTESTING_PROMPT" \
    --max_workers "$MAX_WORKERS" \
    --honeypot_type "$HONEYPOT_TYPE" \
    --pentest_timeout 3600 \
    --benchmark_tasks "static-vs-http-app" \
    --pentest_reasoning_effort "$PENTEST_REASONING_EFFORT" \
    --skip_incomplete

echo "All experiments completed."

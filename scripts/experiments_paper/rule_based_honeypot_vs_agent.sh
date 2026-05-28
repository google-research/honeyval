#!/bin/bash

pentest_models=(
    "vertex_ai/gemini-3-flash-preview-python-curl"
    "anthropic/claude-sonnet-4-6-python-curl"
)

N_SAMPLES=5
MAX_WORKERS=80
HONEYPOT_REASONING_EFFORT="low"
HONEYPOT_INSTRUCTION="none"
HONEYPOT_MODEL="vertex_ai/gemini-3-flash-preview"
PENTESTING_PROMPT="exploit-detect"
HONEYPOT_TYPE="rule-based"
EXPERIMENT_NAME="rule-based-vs-agent"
PENTEST_REASONING_EFFORT="high"

for pentest_model in "${pentest_models[@]}"; do
    echo "----------------------------------------------------------------"
    echo "Running experiment with:"
    echo "  Pentest Model:          $pentest_model"
    echo "----------------------------------------------------------------"

    python src/main.py \
        --mode "run" \
        --meta_experiment_type "$EXPERIMENT_NAME" \
        --pentest_model "$pentest_model" \
        --honeypot_model "$HONEYPOT_MODEL" \
        --honeypot_additional_instructions "$HONEYPOT_INSTRUCTION" \
        --n_samples "$N_SAMPLES" \
        --pentesting_prompt "$PENTESTING_PROMPT" \
        --honeypot_reasoning_effort "$HONEYPOT_REASONING_EFFORT" \
        --max_workers "$MAX_WORKERS" \
        --honeypot_type "$HONEYPOT_TYPE" \
        --pentest_timeout 3600 \
        --pentest_reasoning_effort "$PENTEST_REASONING_EFFORT" \
        --starting_port 15000 \
        --benchmark_tasks "agent-vs-http-app"

    bash scripts/reset_docker_networking_if_stale.sh

    python src/main.py \
        --mode "evaluate" \
        --meta_experiment_type "$EXPERIMENT_NAME" \
        --pentest_model "$pentest_model" \
        --honeypot_model "$HONEYPOT_MODEL" \
        --honeypot_additional_instructions "$HONEYPOT_INSTRUCTION" \
        --n_samples "$N_SAMPLES" \
        --pentesting_prompt "$PENTESTING_PROMPT" \
        --max_workers "$MAX_WORKERS" \
        --honeypot_type "$HONEYPOT_TYPE" \
        --pentest_timeout 3600 \
        --pentest_reasoning_effort "$PENTEST_REASONING_EFFORT" \
        --starting_port 15000 \
        --benchmark_tasks "agent-vs-http-app" \
        --skip_incomplete
        
done

echo "All experiments completed."

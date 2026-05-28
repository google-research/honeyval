#!/bin/bash

pentest_models=(
    "vertex_ai/gemini-3-flash-preview-gemini-cli"
    "anthropic/claude-sonnet-4-6-claude-code"
)

pentesting_prompts=(
    "exploit"
    "exploit-detect"
    "exploit-detect-hide"
)

N_SAMPLES=5
MAX_WORKERS=8
HONEYPOT_REASONING_EFFORT="low"
HONEYPOT_INSTRUCTION="none"
HONEYPOT_MODEL="vertex_ai/gemini-3-flash-preview"
HONEYPOT_TYPE="llm"
EXPERIMENT_NAME="prompts-cli-agent-vs-real"

for pentest_model in "${pentest_models[@]}"; do
    for pentesting_prompt in "${pentesting_prompts[@]}"; do
        echo "----------------------------------------------------------------"
        echo "Running experiment with:"
        echo "  Pentest Model:          $pentest_model"
        echo "  Prompt:                 $pentesting_prompt"
        echo "----------------------------------------------------------------"

        python src/main.py \
            --mode "run" \
            --meta_experiment_type "$EXPERIMENT_NAME" \
            --pentest_model "$pentest_model" \
            --honeypot_model "$HONEYPOT_MODEL" \
            --honeypot_additional_instructions "$HONEYPOT_INSTRUCTION" \
            --n_samples "$N_SAMPLES" \
            --pentesting_prompt "$pentesting_prompt" \
            --honeypot_reasoning_effort "$HONEYPOT_REASONING_EFFORT" \
            --max_workers "$MAX_WORKERS" \
            --honeypot_type "$HONEYPOT_TYPE" \
            --pentest_timeout 3600 \
            --benchmark_tasks "agent-vs-real"

        bash scripts/reset_docker_networking_if_stale.sh

        python src/main.py \
            --mode "evaluate" \
            --meta_experiment_type "$EXPERIMENT_NAME" \
            --pentest_model "$pentest_model" \
            --honeypot_model "$HONEYPOT_MODEL" \
            --honeypot_additional_instructions "$HONEYPOT_INSTRUCTION" \
            --n_samples "$N_SAMPLES" \
            --pentesting_prompt "$pentesting_prompt" \
            --max_workers "$MAX_WORKERS" \
            --honeypot_type "$HONEYPOT_TYPE" \
            --pentest_timeout 3600 \
            --benchmark_tasks "agent-vs-real" \
            --skip_incomplete
            
    done
done

echo "All experiments completed."

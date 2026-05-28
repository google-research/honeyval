#!/bin/bash

honeypot_models=(
    "together_ai/Qwen/Qwen3.5-9B"
    "anthropic/claude-haiku-4-5-20251001"
    "vertex_ai/gemini-3-flash-preview"
    "vertex_ai/gemini-2.5-flash"
    "openai/gpt-5.4-nano"
)

honeypot_instructions=(
    "none"
    "careful_pi"
    "convince"
)

pentest_models=(
    "vertex_ai/gemini-3-flash-preview-gemini-cli"
    "anthropic/claude-sonnet-4-6-claude-code"
)

N_SAMPLES=5
MAX_WORKERS=8
HONEYPOT_REASONING_EFFORT="low"
META_EXPERIMENT_TYPE="llm-honeypot-vs-cli-agent"

for honeypot_instruction in "${honeypot_instructions[@]}"; do
    for honeypot_model in "${honeypot_models[@]}"; do
        for pentest_model in "${pentest_models[@]}"; do
            echo "----------------------------------------------------------------"
            echo "Running experiment with:"
            echo "  Honeypot Model:         $honeypot_model"
            echo "  Honeypot Instruction:   $honeypot_instruction"
            echo "  Pentest Model:          $pentest_model"
            echo "----------------------------------------------------------------"

            python src/main.py \
                --mode "run" \
                --meta_experiment_type $META_EXPERIMENT_TYPE \
                --pentest_model "$pentest_model" \
                --honeypot_model "$honeypot_model" \
                --honeypot_additional_instructions "$honeypot_instruction" \
                --n_samples "$N_SAMPLES" \
                --pentesting_prompt "exploit-detect" \
                --honeypot_reasoning_effort "$HONEYPOT_REASONING_EFFORT" \
                --max_workers "$MAX_WORKERS" \
                --honeypot_type "llm" \
                --pentest_timeout 3600 \
                --benchmark_tasks "agent-vs-http-app"

            bash scripts/reset_docker_networking_if_stale.sh

            python src/main.py \
                --mode "evaluate" \
                --meta_experiment_type $META_EXPERIMENT_TYPE \
                --pentest_model "$pentest_model" \
                --honeypot_model "$honeypot_model" \
                --honeypot_additional_instructions "$honeypot_instruction" \
                --n_samples "$N_SAMPLES" \
                --pentesting_prompt "exploit-detect" \
                --max_workers "$MAX_WORKERS" \
                --honeypot_type "llm" \
                --pentest_timeout 3600 \
                --benchmark_tasks "agent-vs-http-app" \
                --skip_incomplete
                
        done
    done
done

echo "All experiments completed."

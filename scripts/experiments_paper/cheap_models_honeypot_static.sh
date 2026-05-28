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

N_SAMPLES=5
MAX_WORKERS=80
PENTEST_MODEL="vertex_ai/gemini-3-flash-preview"
HONEYPOT_REASONING_EFFORT="low"
PENTEST_REASONING_EFFORT="high"

for honeypot_instruction in "${honeypot_instructions[@]}"; do
    for honeypot_model in "${honeypot_models[@]}"; do
        echo "----------------------------------------------------------------"
        echo "Running experiment with:"
        echo "  Honeypot Model:         $honeypot_model"
        echo "  Honeypot Instruction:   $honeypot_instruction"
        echo "----------------------------------------------------------------"

        python src/main.py \
            --mode "run" \
            --meta_experiment_type "cheap-honeypots" \
            --pentest_model "$PENTEST_MODEL" \
            --honeypot_model "$honeypot_model" \
            --honeypot_additional_instructions "$honeypot_instruction" \
            --n_samples "$N_SAMPLES" \
            --pentesting_prompt "exploit-detect" \
            --honeypot_reasoning_effort "$HONEYPOT_REASONING_EFFORT" \
            --max_workers "$MAX_WORKERS" \
            --honeypot_type "llm" \
            --pentest_timeout 3600 \
            --pentest_reasoning_effort "$PENTEST_REASONING_EFFORT" \
            --benchmark_tasks "static-vs-http-app"

        python src/main.py \
            --mode "evaluate" \
            --meta_experiment_type "cheap-honeypots" \
            --pentest_model "$PENTEST_MODEL" \
            --honeypot_model "$honeypot_model" \
            --honeypot_additional_instructions "$honeypot_instruction" \
            --n_samples "$N_SAMPLES" \
            --pentesting_prompt "exploit-detect" \
            --max_workers "$MAX_WORKERS" \
            --honeypot_type "llm" \
            --pentest_timeout 3600 \
            --pentest_reasoning_effort "$PENTEST_REASONING_EFFORT" \
            --benchmark_tasks "static-vs-http-app" \
            --skip_incomplete

    done
done

echo "All experiments completed."

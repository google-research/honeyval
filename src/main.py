"""
Copyright 2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import json
import multiprocessing
from pathlib import Path

from src.agents import ClaudeCodeAgent, CodexAgent, GeminiCliAgent, SimpleReactAgent
from src.agents.tools import CurlTool, PythonScriptTool
from src.benchmark_apps import all_benchmark_apps
from src.benchmark_prompts import (
    HONEYPOT_ADDITIONAL_INSTRUCTIONS_AGGRESSIVE_PI,
    HONEYPOT_ADDITIONAL_INSTRUCTIONS_CAREFUL_PI,
    HONEYPOT_ADDITIONAL_INSTRUCTIONS_CONVINCE,
    HONEYPOT_ADDITIONAL_INSTRUCTIONS_MISLEADING,
    HONEYPOT_ADDITIONAL_INSTRUCTIONS_VULNERABLE,
    HONEYPOT_DETECTION_PROMPT,
    HONEYPOT_DETECTION_PROMPT_HIDE,
    PENTESTING_PROMPT_EXPLOIT,
    PROMPT_INJECTION_JUDGE_PROMPT,
    REFUSAL_JUDGE_PROMPT,
    AgentPrompt,
)
from src.callbacks import CallbackConfig
from src.http_apps import HttpLLMHoneypot, RuleBasedHttpHoneypot
from src.tasks import BenchmarkRun, all_tasks
from src.utils.constants import (
    COMMAND_INJECTION_DOWNLOAD_TARGET,
    DOCKER_BRIDGE_GATEWAY,
    JUDGE_MODEL,
    JUDGE_REASONING,
    JUDGE_TEMPERATURE,
    SECRET_LAB,
    SECRET_MAPPING,
    TOOL_TIMEOUT,
)
from src.utils.judge import (
    HeuristicLlmPromptInjectionJudge,
    HeuristicLLMRefusalJudge,
    LLMJudge,
)
from src.utils.open_files import set_max_open_files

esc = lambda x: x.replace("/", "-")


def reasoning_effort_suffix(reasoning_effort: str) -> str:
    shorthand = {"low": "l", "medium": "m", "high": "h"}
    return f"-{shorthand.get(reasoning_effort, reasoning_effort)}"


def get_pentest_provider(pentest_model: str) -> str:
    split_pentest = args.pentest_model.split("/")
    if len(split_pentest) < 2:
        raise ValueError(f"No provider found in {pentest_model}")
    else:
        return split_pentest[-2].lower()


def main(args):

    # prepare the benchmark apps
    if "all" in args.benchmark_apps:
        run_benchmark_apps = all_benchmark_apps
    else:
        run_benchmark_apps = []
        available_benchmark_apps = {ba.name: ba for ba in all_benchmark_apps}
        for benchmark_app_name in args.benchmark_apps:
            if benchmark_app_name not in available_benchmark_apps:
                raise ValueError(f"Unknown webapp: {benchmark_app_name}")
            else:
                run_benchmark_apps.append(available_benchmark_apps[benchmark_app_name])

    # prepare the benchmark tasks
    if "all" in args.benchmark_tasks:
        run_benchmark_tasks = all_tasks
    else:
        run_benchmark_tasks = []
        available_benchmark_tasks = {task.name: task for task in all_tasks}
        for task_name in args.benchmark_tasks:
            if task_name not in available_benchmark_tasks:
                raise ValueError(f"Unknown benchmark task: {task_name}")
            else:
                run_benchmark_tasks.append(available_benchmark_tasks[task_name])

    # prepare the honeypot prompt
    match args.honeypot_additional_instructions:
        case "none":
            additional_instructions = ""
        case "careful_pi":
            additional_instructions = HONEYPOT_ADDITIONAL_INSTRUCTIONS_CAREFUL_PI
        case "aggressive_pi":
            additional_instructions = HONEYPOT_ADDITIONAL_INSTRUCTIONS_AGGRESSIVE_PI
        case "mislead":
            additional_instructions = HONEYPOT_ADDITIONAL_INSTRUCTIONS_MISLEADING
        case "convince":
            additional_instructions = HONEYPOT_ADDITIONAL_INSTRUCTIONS_CONVINCE
        case "vulnerable":
            additional_instructions = HONEYPOT_ADDITIONAL_INSTRUCTIONS_VULNERABLE
        case _:
            raise ValueError(
                f"Unknown additional honeypot instructions: {args.honeypot_additional_instructions}"
            )

    # prepare the pentesting prompt
    match args.pentesting_prompt:
        case "exploit":
            pentesting_prompt = AgentPrompt(
                template=PENTESTING_PROMPT_EXPLOIT, secret_lab=SECRET_LAB
            )
        case "exploit-detect":
            pentesting_prompt = AgentPrompt(
                template=PENTESTING_PROMPT_EXPLOIT,
                secret_lab=SECRET_LAB,
                honeypot_detection=HONEYPOT_DETECTION_PROMPT,
            )
        case "exploit-detect-hide":
            pentesting_prompt = AgentPrompt(
                template=PENTESTING_PROMPT_EXPLOIT,
                secret_lab=SECRET_LAB,
                honeypot_detection=HONEYPOT_DETECTION_PROMPT_HIDE,
            )
        case _:
            raise ValueError(
                f"Unknown pentesting prompt type: {args.pentesting_prompt}"
            )

    match args.pentest_model:
        case model_name if model_name.endswith("-gemini-cli"):
            agent = GeminiCliAgent(
                model_name=model_name.removesuffix("-gemini-cli"),
                timeout=args.pentest_timeout,
                max_cost=args.pentest_cost_limit,
            )
        case model_name if model_name.endswith("-codex"):
            agent = CodexAgent(
                model_name=model_name.removesuffix("-codex"),
                timeout=args.pentest_timeout,
                max_cost=args.pentest_cost_limit,
            )
        case model_name if model_name.endswith("-claude-code"):
            agent = ClaudeCodeAgent(
                model_name=model_name.removesuffix("-claude-code"),
                timeout=args.pentest_timeout,
                max_cost=args.pentest_cost_limit,
            )
        case model_name if model_name.endswith("-python-curl"):
            agent = SimpleReactAgent(
                model_name=model_name.removesuffix("-python-curl"),
                temperature=args.pentest_temperature,
                reasoning_effort=args.pentest_reasoning_effort,
                additional_tools={
                    "curl": CurlTool(
                        timeout=TOOL_TIMEOUT,
                        restrict_to_url=f"http://{DOCKER_BRIDGE_GATEWAY}:8000",
                    ),
                    "python_script": PythonScriptTool(timeout=TOOL_TIMEOUT),
                },
                max_steps=args.pentest_max_steps,
                max_cost=args.pentest_cost_limit,
            )
        case model_name if model_name.endswith("-python"):
            agent = SimpleReactAgent(
                model_name=model_name.removesuffix("-python"),
                temperature=args.pentest_temperature,
                reasoning_effort=args.pentest_reasoning_effort,
                additional_tools={
                    "python_script": PythonScriptTool(timeout=TOOL_TIMEOUT),
                },
                max_steps=args.pentest_max_steps,
                max_cost=args.pentest_cost_limit,
            )
        case model_name:
            agent = SimpleReactAgent(
                model_name=model_name,
                temperature=args.pentest_temperature,
                reasoning_effort=args.pentest_reasoning_effort,
                additional_tools={
                    "curl": CurlTool(
                        timeout=TOOL_TIMEOUT,
                        restrict_to_url=f"http://{DOCKER_BRIDGE_GATEWAY}:8000",
                    ),
                },
                max_steps=args.pentest_max_steps,
                max_cost=args.pentest_cost_limit,
            )

    match args.honeypot_type:
        case "llm":
            http_honeypot = HttpLLMHoneypot(
                model_name=args.honeypot_model,
                temperature=args.honeypot_temperature,
                additional_instructions=additional_instructions,
                reasoning_effort=args.honeypot_reasoning_effort,
                add_benchmark_app_additional_description=True,
                max_cost=args.honeypot_cost_limit,
                rate_limit=args.honeypot_rate_limit,
            )
        case "rule-based":
            http_honeypot = RuleBasedHttpHoneypot()
        case _:
            raise ValueError(f"Unknown honeypot type: {args.honeypot_type}")

    match args.pi_judge:

        case "llm":
            prompt_injection_judge = LLMJudge(
                model=JUDGE_MODEL,
                temperature=JUDGE_TEMPERATURE,
                reasoning_effort=JUDGE_REASONING,
                system_prompt=PROMPT_INJECTION_JUDGE_PROMPT,
            )
        case "heuristic-llm":
            _inner_judge = LLMJudge(
                model=JUDGE_MODEL,
                temperature=JUDGE_TEMPERATURE,
                reasoning_effort=JUDGE_REASONING,
                system_prompt=PROMPT_INJECTION_JUDGE_PROMPT,
            )
            prompt_injection_judge = HeuristicLlmPromptInjectionJudge(
                llm_judge=_inner_judge
            )
        case "none":
            prompt_injection_judge = None
        case _:
            raise ValueError(f"Unknown prompt injection judge type: {args.pi_judge}")

    match args.refusal_judge:
        case "llm":
            refusal_judge = LLMJudge(
                model=JUDGE_MODEL,
                temperature=JUDGE_TEMPERATURE,
                reasoning_effort=JUDGE_REASONING,
                system_prompt=REFUSAL_JUDGE_PROMPT,
            )
        case "heuristic-llm":
            _inner_judge = LLMJudge(
                model=JUDGE_MODEL,
                temperature=JUDGE_TEMPERATURE,
                reasoning_effort=JUDGE_REASONING,
                system_prompt=REFUSAL_JUDGE_PROMPT,
            )
            refusal_judge = HeuristicLLMRefusalJudge(llm_judge=_inner_judge)
        case "none":
            refusal_judge = None
        case _:
            raise ValueError(f"Unknown refusal judge type: {args.refusal_judge}")

    pentest_label = (
        f"{esc(args.pentest_model)}"
        f"{reasoning_effort_suffix(args.pentest_reasoning_effort)}"
    )
    honeypot_label = (
        "rule-based"
        if args.honeypot_type == "rule-based"
        else (
            f"{esc(args.honeypot_model)}"
            f"{reasoning_effort_suffix(args.honeypot_reasoning_effort)}"
        )
    )
    base_path = (
        Path(__file__).parent.parent
        / "results"
        / f"{args.meta_experiment_type}"
        / f"{pentest_label}-{args.pentesting_prompt}-{honeypot_label}-{args.honeypot_additional_instructions}"
    )

    callback_config = CallbackConfig(
        ci_target=COMMAND_INJECTION_DOWNLOAD_TARGET[args.ci_target],
        target_password=args.target_password,
        attacker_domain=args.attacker_domain,
    )

    secrets = SECRET_MAPPING[get_pentest_provider(args.pentest_model)]
    secrets.extend([SECRET_LAB, SECRET_LAB.split(" ")[0]])

    benchmark_run = BenchmarkRun(
        subtasks=run_benchmark_tasks,
        benchmark_apps=run_benchmark_apps,
        http_app=http_honeypot,
        agent=agent,
        agent_initial_instruction=pentesting_prompt,
        base_path=base_path,
        secrets=secrets,
        n_samples=args.n_samples,
        prompt_injection_judge=prompt_injection_judge,
        refusal_judge=refusal_judge,
        callback_config=callback_config,
        start_port=args.starting_port,
        max_workers=args.max_workers,
    )

    match args.mode:
        case "run":
            benchmark_run.run(force=args.force)
        case "run-only-metrics":
            benchmark_run.run(force=args.force, only_metrics=True)
        case "evaluate":
            benchmark_run.evaluate(skip_incomplete=args.skip_incomplete)
        case _:
            raise ValueError(f"Mode {args.mode} is not supported.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    multiprocessing.set_start_method("spawn")
    set_max_open_files(16384)

    parser.add_argument(
        "--meta_experiment_type",
        type=str,
        default="benchmark",
        help="Indicate the meta-experiment type of the run. Default benchmark.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["run", "run-only-metrics", "evaluate"],
        required=True,
        help="Choose to run the benchmark or to evaluate the results.",
    )
    parser.add_argument(
        "--n_samples", type=int, default=5, help="Number of samples for each task."
    )
    parser.add_argument(
        "--benchmark_apps",
        nargs="+",
        type=str,
        default=["all"],
        help="List of benchmark apps to run, or 'all'.",
    )
    parser.add_argument(
        "--benchmark_tasks",
        nargs="+",
        type=str,
        default=["all"],
        choices=["all"] + [task.name for task in all_tasks],
        help="List of benchmark tasks to run, or 'all'.",
    )
    parser.add_argument(
        "--pentest_timeout",
        type=int,
        default=600,
        help="Timeout in seconds for container-based agents (Codex, Gemini CLI).",
    )
    parser.add_argument(
        "--pentest_max_steps",
        type=int,
        default=50,
        help="Maximum number of steps the pentesting agent can take.",
    )
    parser.add_argument(
        "--pentest_model",
        type=str,
        help="Pentesting model to use.",
    )
    parser.add_argument(
        "--honeypot_type",
        type=str,
        default="llm",
        choices=["llm", "rule-based"],
        help="Type of honeypot to use: 'llm' for LLM-powered, 'rule-based' for static rule-based.",
    )
    parser.add_argument(
        "--honeypot_model",
        type=str,
        help="Honeypot model to use (only for --honeypot_type llm).",
    )
    parser.add_argument(
        "--honeypot_additional_instructions",
        default="none",
        type=str,
        choices=[
            "none",
            "careful_pi",
            "aggressive_pi",
            "mislead",
            "convince",
            "vulnerable",
        ],
        help="Choose the extra instruction for the honeypot's counterattack.",
    )
    parser.add_argument(
        "--pentest_cost_limit",
        default=10.0,
        type=float,
        help="Set the upper limit (USD) for the pentesting running cost.",
    )
    parser.add_argument(
        "--honeypot_cost_limit",
        default=10.0,
        type=float,
        help="Set the upper limit (USD) for the honeypot running cost.",
    )
    parser.add_argument(
        "--honeypot_rate_limit",
        default=50,
        type=int,
        help="Maximum requests per minute to the honeypot backend. Set to -1 for no limit.",
    )
    parser.add_argument(
        "--pentesting_prompt",
        type=str,
        default="exploit",
        choices=["exploit", "exploit-detect", "exploit-detect-hide"],
        help="Choose the pentesting model's prompt.",
    )
    parser.add_argument(
        "--pentest_temperature",
        type=float,
        default=0.6,
        help="Temperature for sampling in the pentesting agent.",
    )
    parser.add_argument(
        "--pentest_reasoning_effort",
        type=str,
        choices=["low", "medium", "high", "max"],
        default="high",
        help="Set the reasoning effort for the pentesting SimpleReact agent.",
    )
    parser.add_argument(
        "--honeypot_temperature",
        type=float,
        default=0.6,
        help="Temperature for sampling in the honeypot.",
    )
    parser.add_argument(
        "--honeypot_reasoning_effort",
        type=str,
        choices=["low", "medium", "high", "max"],
        default="low",
        help="Set the reasoning effort for the honeypot.",
    )
    parser.add_argument(
        "--pi_judge",
        type=str,
        default="none",
        choices=["none", "llm", "heuristic-llm"],
        help="Select to detect prompt injection attempts.",
    )
    parser.add_argument(
        "--refusal_judge",
        type=str,
        default="none",
        choices=["none", "llm", "heuristic-llm"],
        help="Select to detect agent refusals.",
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=16,
        help="Maximum number of parallel workers.",
    )
    parser.add_argument(
        "--starting_port",
        type=int,
        default=8000,
        help="Start looking for a free port range from this port onwards.",
    )
    parser.add_argument(
        "--ci_target",
        type=str,
        default="llamafactory",
        choices=list(COMMAND_INJECTION_DOWNLOAD_TARGET.keys()),
        help="Command injection download target to use.",
    )
    parser.add_argument(
        "--target_password",
        type=str,
        default="hacked_password",
        help="Target password for the admin password overwrite callback.",
    )
    parser.add_argument(
        "--attacker_domain",
        type=str,
        default="pentest.com",
        help="Attacker domain for the XSS local storage exfiltration callback.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force the execution of the tests, even though this setup has been tested before already.",
    )
    parser.add_argument(
        "--skip_incomplete",
        action="store_true",
        help="Skip incomplete tasks during evaluation.",
    )
    args = parser.parse_args()
    main(args)

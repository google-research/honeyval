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

from src.agents.cli_agent import CliAgent
from src.utils.constants import CLAUDE_CODE_DOCKERFILE, DOCKER_BRIDGE_GATEWAY
from src.utils.litellm_proxy import LiteLLMProxy


class ClaudeCodeAgent(CliAgent):

    DOCKERFILE = CLAUDE_CODE_DOCKERFILE
    AGENT_LABEL = "claude-code"

    def _build_cmd_and_env(
        self,
        proxy: LiteLLMProxy,
        initial_instruction: str,
    ) -> tuple[list[str], dict[str, str]]:
        cmd = [
            "/root/.local/bin/claude",
            "--dangerously-skip-permissions",
            "--model",
            self.model_name,
            "-p",
            initial_instruction,
        ]
        env = {
            "ANTHROPIC_BASE_URL": f"http://{DOCKER_BRIDGE_GATEWAY}:{proxy.port}",
            "ANTHROPIC_AUTH_TOKEN": proxy.api_key,
            "IS_SANDBOX": "1",
        }
        return cmd, env

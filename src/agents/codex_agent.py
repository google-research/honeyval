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
from src.utils.constants import CODEX_DOCKERFILE, DOCKER_BRIDGE_GATEWAY
from src.utils.litellm_proxy import LiteLLMProxy


class CodexAgent(CliAgent):

    DOCKERFILE = CODEX_DOCKERFILE
    AGENT_LABEL = "codex"

    def _build_cmd_and_env(
        self,
        proxy: LiteLLMProxy,
        initial_instruction: str,
    ) -> tuple[list[str], dict[str, str]]:
        cmd = [
            "codex",
            "exec",
            "--yolo",
            "-c",
            "model_provider=litellm",
            "-c",
            "model_providers.litellm.name=litellm",
            "-c",
            f"model_providers.litellm.base_url=http://{DOCKER_BRIDGE_GATEWAY}:{proxy.port}",
            "-c",
            f"model={self.model_name}",
            "-c",
            "model_providers.litellm.env_key=PROXY_API_KEY",
            "-c",
            "model_providers.litellm.wire_api=responses",
            "--skip-git-repo-check",
            initial_instruction,
        ]
        env = {
            "PROXY_API_KEY": proxy.api_key,
        }
        return cmd, env

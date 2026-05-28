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
from src.utils.constants import DOCKER_BRIDGE_GATEWAY, GEMINI_CLI_DOCKERFILE
from src.utils.litellm_proxy import LiteLLMProxy


class GeminiCliAgent(CliAgent):

    DOCKERFILE = GEMINI_CLI_DOCKERFILE
    AGENT_LABEL = "gemini-cli"

    @staticmethod
    def _strip_model_provider(model_name: str) -> str:
        """Strip the router/provider prefix from a model name.

        E.g. 'vertex_ai/gemini-2.5-flash' -> 'gemini-2.5-flash'
        """
        return model_name.split("/", 1)[-1] if "/" in model_name else model_name

    def _build_cmd_and_env(
        self,
        proxy: LiteLLMProxy,
        initial_instruction: str,
    ) -> tuple[list[str], dict[str, str]]:
        cmd = [
            "gemini",
            "--yolo",
            "-p",
            initial_instruction,
        ]
        env = {
            "GEMINI_API_KEY": proxy.api_key,
            "GOOGLE_GEMINI_BASE_URL": f"http://{DOCKER_BRIDGE_GATEWAY}:{proxy.port}",
            "GEMINI_MODEL": self._strip_model_provider(self.model_name),
        }
        return cmd, env

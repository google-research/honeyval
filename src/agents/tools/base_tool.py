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

from abc import ABC, abstractmethod

from src.sandkasten import DockerSandkasten


class BaseTool(ABC):
    """
    A very simple inteface to handle tool implementations and calls.
    """

    def __init__(self):
        self.name: str
        self.description: str
        self._set_name_and_desc()

    def __str__(self) -> str:
        return f"Tool Name: {self.name}\nTool Description: {self.description}"

    @abstractmethod
    def _set_name_and_desc(self) -> None:
        pass

    @abstractmethod
    def __call__(self, tool_input: str, sandbox: DockerSandkasten) -> str:
        pass

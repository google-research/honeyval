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

import json
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from logging import Logger
from pathlib import Path
from typing import Dict, List, Protocol

import requests


class CallbackType(Enum):
    COMMAND_INJECTION = "command_injection"
    SQL_INJECTION = "sql_injection"
    OVERWRITE_ADMIN_PASSWORD = "overwrite_admin_password"
    EXFIL_LOCAL_STORAGE = "exfil_local_storage"


class FunctionalTest(Protocol):

    def __call__(self, port: int, logger: Logger) -> bool: ...


class RegisterAdminFn(Protocol):

    def __call__(self, front_port: int, password: str, logger: Logger) -> None: ...


class LoginAdminFn(Protocol):

    def __call__(
        self, front_port: int, password: str, logger: Logger
    ) -> requests.Response: ...


@dataclass(frozen=True)
class RealApp:

    name: str
    code_path: Path
    cwe_path: Path

    @cached_property
    def vulnerabilities(self) -> Dict[str, Dict[str, str]]:
        with open(self.cwe_path, "r") as f:
            vuls = json.load(f)
        return vuls

    @property
    def tag(self) -> str:
        if self.vulnerabilities:
            return "vul"
        else:
            return "sec"

    @property
    def id(self) -> str:
        return self.name + "-" + self.tag

    @property
    def secure(self) -> bool:
        return not bool(self.vulnerabilities)

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class BenchmarkApp:

    name: str
    base_path: Path
    openapi_config_path: Path

    functional_tests: List[FunctionalTest]

    # This is only filled for apps where an admin user is pre-registered
    admin_auth_details: Dict[str, str] | None = None
    register_admin_fn: RegisterAdminFn | None = None
    login_admin_fn: LoginAdminFn | None = None

    # XSS target endpoint -- used only for apps where we want to run the XSS verifier against the vulnerable app's output
    xss_target_endpoint: str | None = None

    callback_type: CallbackType | None = None

    additional_description: str = ""
    honeypot_additional_description: str = ""

    real_apps: List[RealApp] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "real_apps",
            self._make_real_apps(),
        )

    def _make_real_apps(self) -> List[RealApp]:
        return [
            RealApp(
                name=self.name,
                code_path=self.base_path / f"{tag}/app.py",
                cwe_path=self.base_path / f"{tag}/cwes.json",
            )
            for tag in ["sec", "vul"]
        ]

    @property
    def potential_vulnerabilities(self) -> Dict[str, Dict[str, str]]:
        return {
            cwe: meta_data
            for real_app in self.real_apps
            for cwe, meta_data in real_app.vulnerabilities.items()
        }

    @cached_property
    def openapi_config(self) -> str:
        with open(self.openapi_config_path, "r") as f:
            cfg = f.read()
        cfg = "\n".join(l for l in cfg.split("\n") if not l.startswith("#"))
        return cfg.strip()

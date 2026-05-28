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

from src.benchmark_apps.base_benchmark_app import BenchmarkApp, CallbackType
from src.callbacks.base import BaseContainerCallback
from src.callbacks.config import CallbackConfig
from src.callbacks.delete_table import DeleteTableCallback
from src.callbacks.exfil_local_storage import ExfilLocalStorageCallback
from src.callbacks.find_file import FindFileCallback
from src.callbacks.overwrite_admin_password import OverwriteAdminPasswordCallback


def make_callback(
    benchmark_app: BenchmarkApp,
    config: CallbackConfig,
) -> BaseContainerCallback | None:
    """Return the appropriate callback for the given benchmark app, or None if the app
    has no associated callback."""
    match benchmark_app.callback_type:
        case CallbackType.COMMAND_INJECTION:
            return FindFileCallback(benchmark_app, ci_target=config.ci_target)
        case CallbackType.SQL_INJECTION:
            return DeleteTableCallback(benchmark_app)
        case CallbackType.OVERWRITE_ADMIN_PASSWORD:
            return OverwriteAdminPasswordCallback(
                benchmark_app, target_password=config.target_password
            )
        case CallbackType.EXFIL_LOCAL_STORAGE:
            return ExfilLocalStorageCallback(
                benchmark_app, attacker_domain=config.attacker_domain
            )
        case _:
            return None

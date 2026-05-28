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

from pathlib import Path

from src.benchmark_apps.base_benchmark_app import BenchmarkApp, CallbackType
from src.utils.name_conversion import camel_to_lower
from third_party.baxbench.scenario_tests.product_catalog import functional_tests

NAME = "ProductCatalog"
BASE_PATH = Path(__file__).parent.parent.parent / f"data/baxbench-webapps/{NAME}"
CONFIG_BASE_PATH = (
    Path(__file__).parent.parent.parent
    / "third_party"
    / "baxbench"
    / "openapi_specifications"
)

ProductCatalog = BenchmarkApp(
    name=NAME,
    base_path=BASE_PATH,
    openapi_config_path=CONFIG_BASE_PATH / (camel_to_lower(NAME) + ".yaml"),
    functional_tests=functional_tests,
    callback_type=CallbackType.COMMAND_INJECTION,
)

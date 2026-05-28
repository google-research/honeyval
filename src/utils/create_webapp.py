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

import subprocess
from logging import Logger
from pathlib import Path
from typing import List


def create_webapp(
    template_dir: Path,
    openapi_scheme: Path,
    output_dir: Path,
    llm_port: int,
    suppress_print: bool = True,
) -> None:
    """
    Programmatically and safely runs the fastapi-codegen command.

    Args:
        template_dir (Path): Path to the template directory.
        openapi_scheme (Path): Path to the input YAML file.
        output_dir (Path): Path to the output directory.
        llm_port (int): The port that will be hard-coded in the generated application
            for communicating with the llm backend.
        suppress_print (bool): Toggle to suppress the success message. Useful
            when generating apps in bulk.
    """
    command: List[str] = [
        "fastapi-codegen",
        "-t",
        str(template_dir),
        "--input",
        str(openapi_scheme),
        "--output",
        str(output_dir),
    ]

    try:
        subprocess.run(
            command, check=True, capture_output=True, text=True, encoding="utf-8"
        )

        with open(output_dir / "main.py", "r") as f:
            app = f.read()

        with open(output_dir / "models.py", "r") as f:
            models = f.read()

        # add port
        app = app.replace("<PORT>", str(llm_port))

        # remove secret string typing
        models = models.replace("[SecretStr]", "[str]")

        with open(output_dir / "main.py", "w") as f:
            f.write(app)

        with open(output_dir / "models.py", "w") as f:
            f.write(models)

        if not suppress_print:
            print(f"The webapp has been created and is runnable under {output_dir}.")
    except FileNotFoundError:
        raise FileNotFoundError(
            f"app.py was not found on the path: {output_dir}. Perhaphs fastapi-codegen failed."
        )
    except Exception as e:
        raise e


if __name__ == "__main__":

    import tqdm

    config_dir = (
        Path(__file__).parent.parent.parent / "configs/llm_honeypot/baxbench_webapps"
    )
    template_dir = Path(__file__).parent.parent.parent / "templates"
    target_dir = Path(__file__).parent.parent.parent / "webapps"
    target_dir.mkdir(exist_ok=True, parents=True)

    yaml_extensions = (".yaml", ".yml")

    configs = {
        f.stem: f.name
        for f in config_dir.iterdir()
        if f.is_file() and f.suffix in yaml_extensions
    }

    for app_name, app_config in tqdm.tqdm(configs.items()):
        create_webapp(
            template_dir=template_dir,
            openapi_scheme=config_dir / app_config,
            output_dir=target_dir / app_name,
            llm_port=8001,
        )

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

import tempfile
from logging import Logger
from pathlib import Path

import docker


def build_image_if_needed(
    dockerfile: str, tag: str, logger: Logger | None = None, verbose: bool = False
) -> None:
    """
    Checks if an image with a certain tag exists. If yes, then it simply exits.
    Otherwise, the image is build from the provided dockerfile.

    Args:
        dockerfile (str): The dockerfile from which the image will be built if no
            image is found corresponding to the tag.
        tag (str): The sought image tag.
        logger (logging.Logger or None): Optional logger.
        verbose (bool): Print the progress.
    """

    client = docker.from_env()

    try:
        client.images.get(tag)
        if logger:
            logger.info(f"Image {tag} found on the system.")
        if verbose:
            print(f"Image {tag} found on the system.")
    except docker.errors.ImageNotFound:
        if logger:
            logger.info(f"Image {tag} not found on the system. Building.")
        if verbose:
            print(f"Image {tag} not found on the system. Building.")
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(Path(temp_dir) / "Dockerfile", "w") as f:
                f.write(dockerfile)

            try:
                client.images.build(path=temp_dir, tag=tag, rm=True)
                if logger:
                    logger.info("Image built successfully.")
                if verbose:
                    print("Image built successfully.")
            except docker.errors.BuildError as e:
                err = ""
                for line in e.build_log:
                    if "stream" in line:
                        err += line["stream"].strip()
                        err += "\n"
                if logger:
                    logger.error(f"Error building the image:\n{err}")
                if verbose:
                    print(f"Error building the image:\n{err}")
                raise
    finally:
        client.close()

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

import resource


def set_max_open_files(desired_limit: int):
    """
    Attempts to raise the open file limit (ulimit -n) to the desired number.

    Args:
        desired_limit (int): The target desired limit.

    Raises:
        ValueError if the limit raising fails.
    """
    _, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)

    if hard_limit < desired_limit:
        print(
            f"WARNING: System hard limit ({hard_limit}) is lower than desired ({desired_limit})."
        )
        target_limit = hard_limit
    else:
        target_limit = desired_limit

    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target_limit, hard_limit))

        # Verify
        new_soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)

        if new_soft < desired_limit:
            print(
                f"Warning: Could not reach the desired {desired_limit} limit (restricted by OS at {hard_limit})."
            )

    except ValueError as e:
        print(f"Failed to change limits: {e}")

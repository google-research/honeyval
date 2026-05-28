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

import socket
from time import sleep, time
from typing import List


def wait_until_port_is_free(
    port: int, host: str = "127.0.0.1", timeout: int = 600
) -> None:
    """
    Blocks execution until a given port is freed.

    Args:
        port (int): The port to wait for.
        host (str): Host address.
        timeout (int): Maximum time to wait in seconds.

    Raises:
        TimeoutError if the port is still not released after 'timeout' seconds.
    """
    start = time()
    while is_port_in_use(port, host):
        if time() - start > timeout:
            raise TimeoutError("The port was not freed in time.")
        sleep(1.0)


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """
    Checks if a given port is currently in use on the specified host.

    Args:
        port (int): The port to check.
        host (str): Host address.

    Returns:
        True if the port is in use, otherwise false.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_free_ports(start_port: int, count: int, host: str = "127.0.0.1") -> List[int]:
    """
    Finds a 'count' number of free ports.

    Args:
        start_port (int): The port number to begin the search from.
        count (int): The number of free ports required.
        host (str): The host address to check for port availability.

    Returns:
        List of free ports. Raises a RuntimeError if not enough ports could be found.
    """
    if not 1024 <= start_port <= 65535:
        raise ValueError(
            "Start port must be within the registered or dynamic range (1024-65535)."
        )
    if count <= 0:
        raise ValueError("Count must be a positive integer.")

    current_port = start_port
    available_ports = []
    while current_port <= 65535:
        if not is_port_in_use(current_port, host):
            available_ports.append(current_port)
        current_port += 1
        if len(available_ports) >= count:
            return available_ports

    raise RuntimeError(
        f"Could not find a free range of {count} ports starting from {start_port}."
    )

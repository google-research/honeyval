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

import re
import subprocess
from logging import Logger
from typing import Tuple

import docker
from docker.models.containers import Container

from src.utils.docker_utils import build_image_if_needed


class DockerSandkasten:

    def __init__(
        self,
        name: str,
        image: Tuple[str, str],
        logger: Logger,
        network_mode: str = "host",
        front_port: int | None = None,
    ) -> None:
        self.name = name
        self.image = image
        self.logger = logger
        self.network_mode = network_mode
        self.front_port = front_port

        self.client: docker.DockerClient | None = None
        self.container: Container | None = None
        self.container_ip: str | None = None
        self._network_restrictions_applied = False

    def _docker_network_mode(self) -> str:
        return "bridge" if self.network_mode == "sandboxed" else self.network_mode

    def _resolve_current_container_ip(self) -> str | None:
        """Return the current container IP used to scope iptables cleanup."""
        if self.container is None:
            return None

        self.container.reload()
        networks = self.container.attrs["NetworkSettings"].get("Networks", {})
        for network_name, network_settings in networks.items():
            ip_address = network_settings.get("IPAddress")
            if ip_address:
                self.logger.info(
                    f"Using container IP {ip_address} from Docker network '{network_name}' for iptables scoping."
                )
                return ip_address
        self.logger.info(
            "Container has no per-container IP address in its current network mode; no stale iptables cleanup is needed."
        )
        return None

    def _apply_host_network_restrictions(
        self,
        container_ip: str,
        front_port: int,
    ) -> None:
        """Restrict sandbox traffic to the host app port."""
        rules = [
            [
                "sudo",
                "/sbin/iptables",
                "-I",
                "DOCKER-USER",
                "-s",
                container_ip,
                "-j",
                "DROP",
            ],
            ["sudo", "/sbin/iptables", "-I", "INPUT", "-s", container_ip, "-j", "DROP"],
            [
                "sudo",
                "/sbin/iptables",
                "-I",
                "INPUT",
                "-s",
                container_ip,
                "-p",
                "tcp",
                "--dport",
                str(front_port),
                "-j",
                "ACCEPT",
            ],
        ]
        for rule in rules:
            result = subprocess.run(rule, capture_output=True)
            if result.returncode != 0:
                self.logger.warning(
                    f"iptables insert failed (exit={result.returncode}): {' '.join(rule)}\n"
                    f"{result.stderr.decode('utf-8', errors='replace')}"
                )
        self.logger.info(
            f"Sandbox network restrictions applied for container {container_ip}."
        )

    def _cleanup_stale_network_restrictions(self, container_ip: str) -> None:
        """Remove leaked iptables rules for exactly one container IP."""
        ip_pat = re.compile(r"-s\s+(\S+)")
        for chain in ("INPUT", "DOCKER-USER"):
            result = subprocess.run(
                ["sudo", "/sbin/iptables", "-S", chain], capture_output=True, text=True
            )
            if result.returncode != 0:
                self.logger.warning(
                    f"Cannot list {chain} rules: {result.stderr.strip()}"
                )
                continue
            for line in result.stdout.splitlines():
                if not line.startswith("-A"):
                    continue
                match = ip_pat.search(line)
                if not match:
                    continue
                src = match.group(1).split("/")[0]
                if src != container_ip:
                    continue
                delete_cmd = ["sudo", "/sbin/iptables", "-D", *line.split()[1:]]
                delete_result = subprocess.run(delete_cmd, capture_output=True)
                if delete_result.returncode != 0:
                    self.logger.warning(
                        f"Failed to remove stale rule: {' '.join(delete_cmd)}\n"
                        f"{delete_result.stderr.decode('utf-8', errors='replace')}"
                    )
                else:
                    self.logger.info(f"Removed stale iptables rule: {line.strip()}")

    def _remove_host_network_restrictions(
        self,
        container_ip: str,
        front_port: int,
    ) -> None:
        rules = [
            [
                "sudo",
                "/sbin/iptables",
                "-D",
                "DOCKER-USER",
                "-s",
                container_ip,
                "-j",
                "DROP",
            ],
            ["sudo", "/sbin/iptables", "-D", "INPUT", "-s", container_ip, "-j", "DROP"],
            [
                "sudo",
                "/sbin/iptables",
                "-D",
                "INPUT",
                "-s",
                container_ip,
                "-p",
                "tcp",
                "--dport",
                str(front_port),
                "-j",
                "ACCEPT",
            ],
        ]
        for rule in rules:
            result = subprocess.run(rule, capture_output=True)
            if result.returncode != 0:
                self.logger.warning(
                    f"iptables delete failed (exit={result.returncode}): {' '.join(rule)}\n"
                    f"{result.stderr.decode('utf-8', errors='replace')}"
                )
        self.logger.info(
            f"Sandbox network restrictions removed for container {container_ip}."
        )

    def _cleanup_network_restrictions(self) -> None:
        if (
            not self._network_restrictions_applied
            or self.container_ip is None
            or self.front_port is None
        ):
            return
        self._remove_host_network_restrictions(
            container_ip=self.container_ip,
            front_port=self.front_port,
        )
        self.container_ip = None
        self._network_restrictions_applied = False

    def _teardown_container(self) -> None:
        if self.container is None:
            return
        try:
            self.container.reload()
            container_logs = self.container.logs(stdout=True, stderr=True, follow=False)
            self.logger.info(
                f"Container logs of the sandbox:\n{container_logs.decode('utf-8', errors='replace')}"
            )
            self.container.stop(timeout=15)
            self.container.remove(force=True)
            self.logger.info("The sandbox container has been removed successfully.")
        except docker.errors.NotFound:
            self.logger.warning(
                "The sandbox container was not found. It might have been removed already."
            )
        except Exception as e:
            self.logger.warning(
                f"An unexpected error occurred when trying to tear down the sandbox container:\n{e}"
            )
        finally:
            self.container = None

    def __enter__(self) -> "DockerSandkasten":
        if self.network_mode == "sandboxed" and self.front_port is None:
            raise ValueError(
                "front_port must be set when DockerSandkasten runs in sandboxed network mode."
            )

        build_image_if_needed(
            dockerfile=self.image[0],
            tag=self.image[1],
            logger=self.logger,
        )
        self.client = docker.from_env()

        self.logger.info(f"Creating the sandbox container. Tag: {self.name}")
        try:
            self.container = self.client.containers.run(
                image=self.image[1],
                detach=True,
                name=self.name,
                network_mode=self._docker_network_mode(),
                working_dir="/sandbox",
                auto_remove=False,
                command="sleep infinity",
            )
            self.container_ip = self._resolve_current_container_ip()
            if self.container_ip is not None:
                self._cleanup_stale_network_restrictions(self.container_ip)
            if self.network_mode == "sandboxed":
                if self.container_ip is None:
                    raise ValueError(
                        "Could not determine the current IP of the sandbox container."
                    )
                front_port = self.front_port
                if front_port is None:
                    raise ValueError(
                        "front_port must be set when DockerSandkasten runs in sandboxed network mode."
                    )
                self._apply_host_network_restrictions(
                    container_ip=self.container_ip,
                    front_port=front_port,
                )
                self._network_restrictions_applied = True
        except Exception as e:
            self.logger.error(f"An unexpected error occurred:\n{e}")
            self._cleanup_network_restrictions()
            self._teardown_container()
            if self.client is not None:
                self.client.close()
                self.client = None
            raise

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.logger.info(f"Stopping and removing sandbox container '{self.name}'...")
        try:
            self._cleanup_network_restrictions()
            self._teardown_container()
        finally:
            if self.client is not None:
                self.client.close()
                self.client = None

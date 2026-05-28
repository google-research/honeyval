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

"""
Standalone LiteLLM callback for the proxy subprocess.

This module is loaded by litellm's proxy via the config file reference
"litellm_logger.proxy_handler_instance". It must be self-contained
(no imports from src.*) because it runs inside the litellm subprocess.

Configuration via environment variables:
  PROXY_TRACE_LOG_PATH  -- path to the JSONL output file
"""

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger


class ProxyTraceLogger(CustomLogger):

    def __init__(self):
        super().__init__()
        self._log_path = Path(
            os.environ.get(
                "PROXY_TRACE_LOG_PATH",
                f"/tmp/litellm_proxy_trace-{uuid.uuid4().hex[:8]}.jsonl",
            )
        )
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._seen_time_ins: set[float] = set()
        self._lock = threading.Lock()

    def _write_event(self, event: dict) -> None:
        # Deduplicate by time_in: for the /responses endpoint LiteLLM fires
        # both sync+async success callbacks AND spurious sync+async failure
        # callbacks for every call, all sharing the same time_in.
        # First event for a given time_in wins; all others are dropped.
        # Events without time_in (e.g. terminal SUCCESS/GIVEUP) are always written.
        time_in = event.get("time_in")
        if time_in is not None:
            with self._lock:
                if time_in in self._seen_time_ins:
                    return
                self._seen_time_ins.add(time_in)
        with open(self._log_path, "a") as f:
            f.write(json.dumps(event) + "\n")

    @staticmethod
    def _to_timestamp(t) -> float:
        if isinstance(t, datetime):
            return t.timestamp()
        return float(t)

    def _build_success_event(self, kwargs, response_obj, start_time, end_time) -> dict:
        slo = kwargs.get("standard_logging_object") or {}

        messages = slo.get("messages") or kwargs.get("input")
        model = slo.get("model") or kwargs.get("model", "unknown")
        prompt_tokens = slo.get("prompt_tokens", 0)
        completion_tokens = slo.get("completion_tokens", 0)

        response_dict = None
        if response_obj is not None:
            try:
                response_dict = response_obj.model_dump()
            except Exception:
                response_dict = str(response_obj)

        raw_response = None
        tool_calls = None
        if response_obj is not None:
            # Responses API: extract last assistant message from output[]
            try:
                for item in reversed(response_obj.output):
                    if (
                        getattr(item, "type", None) == "message"
                        and getattr(item, "role", None) == "assistant"
                    ):
                        texts = [
                            p.text
                            for p in item.content
                            if getattr(p, "type", None) == "output_text"
                            and getattr(p, "text", None)
                        ]
                        if texts:
                            raw_response = "\n".join(texts)
                        break
            except Exception:
                pass

            # Chat Completions API fallback for raw_response
            if raw_response is None:
                try:
                    raw_response = response_obj.choices[0].message.content
                except Exception:
                    pass

            # Tool calls: Responses API (function_call items in output)
            try:
                fc_items = [
                    item.model_dump()
                    for item in response_obj.output
                    if getattr(item, "type", None) == "function_call"
                ]
                if fc_items:
                    tool_calls = fc_items
            except Exception:
                pass

            # Tool calls: Chat Completions API fallback
            if tool_calls is None:
                try:
                    tc = response_obj.choices[0].message.tool_calls
                    if tc is not None:
                        tool_calls = [t.model_dump() for t in tc]
                except Exception:
                    pass

        # Token detail: reasoning_tokens, cached_tokens, cache_write_tokens
        reasoning_tokens = 0
        cached_tokens = 0
        cache_write_tokens = 0
        if response_dict and isinstance(response_dict, dict):
            usage = response_dict.get("usage") or {}
            reasoning_tokens = (usage.get("completion_tokens_details") or {}).get(
                "reasoning_tokens"
            ) or 0
            cached_tokens = (usage.get("prompt_tokens_details") or {}).get(
                "cached_tokens"
            ) or 0
            cache_write_tokens = usage.get("cache_creation_input_tokens") or 0

        return {
            "time_in": self._to_timestamp(start_time),
            "time_out": self._to_timestamp(end_time),
            "event": "llm_call",
            "raw_response": raw_response,
            "action_body": None,
            "env_response": None,
            "tokens_consumed": prompt_tokens,
            "tokens_generated": completion_tokens,
            "reasoning_tokens": reasoning_tokens,
            "cached_tokens": cached_tokens,
            "cache_write_tokens": cache_write_tokens,
            "model": model,
            "messages": messages,
            "response": response_dict,
            "tool_calls": tool_calls,
            "status": "success",
        }

    def _build_failure_event(self, kwargs, response_obj, start_time, end_time) -> dict:
        slo = kwargs.get("standard_logging_object") or {}

        response_dict = None
        if response_obj is not None:
            try:
                response_dict = response_obj.model_dump()
            except Exception:
                response_dict = str(response_obj)

        reasoning_tokens = 0
        cached_tokens = 0
        cache_write_tokens = 0
        if response_dict and isinstance(response_dict, dict):
            usage = response_dict.get("usage") or {}
            reasoning_tokens = (usage.get("completion_tokens_details") or {}).get(
                "reasoning_tokens"
            ) or 0
            cached_tokens = (usage.get("prompt_tokens_details") or {}).get(
                "cached_tokens"
            ) or 0
            cache_write_tokens = usage.get("cache_creation_input_tokens") or 0

        return {
            "time_in": self._to_timestamp(start_time),
            "time_out": self._to_timestamp(end_time),
            "event": "llm_call_failure",
            "raw_response": None,
            "action_body": None,
            "env_response": None,
            "tokens_consumed": slo.get("prompt_tokens", 0),
            "tokens_generated": slo.get("completion_tokens", 0),
            "reasoning_tokens": reasoning_tokens,
            "cached_tokens": cached_tokens,
            "cache_write_tokens": cache_write_tokens,
            "model": slo.get("model") or kwargs.get("model", "unknown"),
            "messages": slo.get("messages") or kwargs.get("input"),
            "response": response_dict,
            "tool_calls": None,
            "error_str": slo.get("error_str", str(response_obj)),
            "status": "failure",
        }

    # Sync hooks (used by litellm library calls)
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._write_event(
            self._build_success_event(kwargs, response_obj, start_time, end_time)
        )

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self._write_event(
            self._build_failure_event(kwargs, response_obj, start_time, end_time)
        )

    # Async hooks (used by litellm proxy which runs under uvicorn)
    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._write_event(
            self._build_success_event(kwargs, response_obj, start_time, end_time)
        )

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self._write_event(
            self._build_failure_event(kwargs, response_obj, start_time, end_time)
        )


proxy_handler_instance = ProxyTraceLogger()

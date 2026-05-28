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
Shared LLM cost calculation utilities.
"""


def compute_llm_cost(
    input_tokens: int,
    output_tokens: int,
    costs: dict[str, float],
    cached_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Compute dollar cost for a single LLM call.

    Args:
        input_tokens: Total prompt tokens (including cached and cache_write portions).
        output_tokens: Completion tokens generated.
        costs: Pricing dict with 'input' and 'output' keys (USD per 1M tokens).
               Optional 'cached' and 'cache_write' keys for discounted rates;
               both fall back to costs['input'] if absent.
        cached_tokens: Prompt tokens served from cache.
        cache_write_tokens: Prompt tokens written to cache.

    Returns:
        Dollar cost.
    """
    if "cache_write" not in costs:
        regular_tokens = input_tokens - cached_tokens
        return (
            regular_tokens / 1e6 * costs["input"]
            + cached_tokens / 1e6 * costs.get("cached", costs["input"])
            + output_tokens / 1e6 * costs["output"]
        )
    else:
        regular_tokens = input_tokens - cached_tokens - cache_write_tokens
        return (
            regular_tokens / 1e6 * costs["input"]
            + cached_tokens / 1e6 * costs.get("cached", costs["input"])
            + cache_write_tokens / 1e6 * costs.get("cache_write", costs["input"])
            + output_tokens / 1e6 * costs["output"]
        )


def compute_llm_cost_from_events(
    events: list[dict],
    costs: dict[str, float],
) -> float:
    """Compute total dollar cost by summing token fields across metadata event dicts.

    Recognised event fields: tokens_consumed, tokens_generated, cached_tokens,
    cache_write_tokens.  Missing fields default to 0.

    Args:
        events: List of metadata event dicts.
        costs: Pricing dict (see compute_llm_cost).

    Returns:
        Total dollar cost.
    """
    total_cost = 0.0
    for event in events:
        input_tokens = event.get("tokens_consumed", 0)
        output_tokens = event.get("tokens_generated", 0)
        cached_tokens = event.get("cached_tokens", 0)
        cache_write_tokens = event.get("cache_write_tokens", 0)
        total_cost += compute_llm_cost(
            input_tokens, output_tokens, costs, cached_tokens, cache_write_tokens
        )
    return total_cost

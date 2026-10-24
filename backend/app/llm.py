"""DeepSeek (OpenAI-compatible) tool-calling loop + record/replay cache.

Every agent calls `run_agent(...)`. Tools are plain Python functions; the LLM decides which to call,
reads the results and returns a final JSON object.

Replay: each run records the raw LLM messages to replay_cache/<tag>.json. With REPLAY=1 the loop
reads those instead of calling the API (tools still execute live), so the demo works offline.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from openai import AsyncOpenAI

CACHE = Path(__file__).resolve().parents[1] / "replay_cache"
MAX_STEPS = 10


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON schema of kwargs
    fn: Callable[..., Any]

    def spec(self) -> dict:
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": self.parameters}}


def _to_jsonable(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"no JSON object in LLM output: {text[:200]}")
    return json.loads(text[start:end + 1])


class _Replayer:
    def __init__(self, tag: str):
        self.path = CACHE / f"{tag}.json"
        self.replay = os.getenv("REPLAY") == "1"
        self.recorded: list[dict] = json.loads(self.path.read_text("utf-8")) if self.replay else []
        self.i = 0

    async def complete(self, client: AsyncOpenAI | None, **kw) -> dict:
        if self.replay:
            if self.i >= len(self.recorded):
                raise RuntimeError(f"replay cache {self.path.name} exhausted at step {self.i}")
            msg = self.recorded[self.i]
            self.i += 1
            return msg
        resp = await client.chat.completions.create(**kw)
        m = resp.choices[0].message
        msg = {"role": "assistant", "content": m.content or ""}
        if m.tool_calls:
            msg["tool_calls"] = [{"id": c.id, "type": "function",
                                  "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                 for c in m.tool_calls]
        self.recorded.append(msg)
        return msg

    def save(self) -> None:
        if not self.replay:
            CACHE.mkdir(exist_ok=True)
            self.path.write_text(json.dumps(self.recorded, ensure_ascii=False, indent=1), "utf-8")


def _client() -> AsyncOpenAI | None:
    if os.getenv("REPLAY") == "1":
        return None
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY missing (or set REPLAY=1)")
    return AsyncOpenAI(api_key=key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))


async def run_agent(*, tag: str, agent: str, system: str, user: str, tools: list[Tool],
                    emit: Callable[..., Any], vehicle_id: str | None = None) -> dict:
    """Run the tool loop until the model answers with a JSON object. `emit` = state.emit."""
    client = _client()
    rep = _Replayer(tag)
    by_name = {t.name: t for t in tools}
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    try:
        for _ in range(MAX_STEPS):
            msg = await rep.complete(client, model=model, messages=messages, temperature=0.2,
                                     tools=[t.spec() for t in tools] if tools else None)
            messages.append(msg)
            calls = msg.get("tool_calls") or []
            if msg["content"] and calls:
                emit(agent, "thought", "Raisonnement", msg["content"], vehicle_id=vehicle_id)
            if not calls:
                try:
                    return parse_json(msg["content"])
                except (ValueError, json.JSONDecodeError):
                    messages.append({"role": "user", "content": "Réponds uniquement avec l'objet JSON final demandé."})
                    continue
            for c in calls:
                name, raw = c["function"]["name"], c["function"]["arguments"] or "{}"
                args = json.loads(raw)
                emit(agent, "tool_call", name, raw, vehicle_id=vehicle_id, args=args)
                try:
                    result = _to_jsonable(by_name[name].fn(**args))
                except Exception as e:  # tool errors go back to the model, not up the stack
                    result = {"error": f"{type(e).__name__}: {e}"}
                text = json.dumps(result, ensure_ascii=False)
                emit(agent, "tool_result", name, text[:600], vehicle_id=vehicle_id)
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": text})
        raise RuntimeError(f"{agent}: no final answer after {MAX_STEPS} steps")
    finally:
        rep.save()

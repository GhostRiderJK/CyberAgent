"""
LLM client for CyberAgent, configured entirely through environment variables
(.env / shell), so keys and endpoints can be changed without touching config.yaml.

Backends (LLM_BACKEND):
  ollama  - native Ollama /api/chat endpoint
  openai  - any OpenAI-compatible /v1/chat/completions server
            (vLLM, LM Studio, OpenAI itself, ...)
  mock    - deterministic offline stub (default; keeps tests running)

Environment variables:
  LLM_BACKEND   = ollama | openai | mock
  LLM_BASE_URL  = e.g. http://localhost:11434       (ollama, also the default)
                  or http://<host>:<port>/v1        (openai)
  LLM_API_KEY   = bearer token for the endpoint (masked; keep local)
  LLM_MODEL     = model id, for ollama the name of a pulled model
  LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT_S
"""
import json
import os
from typing import Any, Dict, List, Optional

import httpx


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self):
        # Load .env if present (no-op when dotenv is unavailable)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        self.backend = (_env("LLM_BACKEND") or "mock").lower()
        self.base_url = _env("LLM_BASE_URL") or ""
        self.api_key = _env("LLM_API_KEY") or ""
        self.model = _env("LLM_MODEL") or ""
        self.temperature = float(_env("LLM_TEMPERATURE", "0"))
        self.max_tokens = int(_env("LLM_MAX_TOKENS", "1024"))
        self.timeout = float(_env("LLM_TIMEOUT_S", "120"))

    @property
    def available(self) -> bool:
        if self.backend == "mock":
            return False
        if self.backend == "openai":
            return bool(self.base_url and self.model)
        if self.backend == "ollama":
            return bool((self.base_url or "http://localhost:11434") and self.model)
        return False

    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None) -> str:
        """Send a chat request and return the assistant text."""
        if self.backend == "mock":
            return self._mock_response(messages)
        if self.backend == "openai":
            return self._chat_openaiCompatible(messages, max_tokens)
        if self.backend == "ollama":
            return self._chat_ollama(messages, max_tokens)
        raise LLMError(f"Unknown LLM backend: {self.backend}")

    def chat_json(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Chat request whose reply must be a JSON object."""
        try:
            text = self.chat(messages, max_tokens=max_tokens)
            return self._extract_json(text)
        except LLMError:
            # Reasoning models sometimes spend the budget on analysis prose.
            retry = list(messages) + [{
                "role": "user",
                "content": "Your previous reply contained no complete JSON object. Reply again with ONLY the JSON object, no analysis, no preamble.",
            }]
            text = self.chat(retry, max_tokens=max_tokens)
            return self._extract_json(text)

    # ---- backends -------------------------------------------------------

    def _chat_openaiCompatible(self, messages: List[Dict[str, str]], max_tokens: Optional[int]) -> str:
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMError(f"OpenAI-compatible LLM call failed ({url}): {e}") from e

    def _chat_ollama(self, messages: List[Dict[str, str]], max_tokens: Optional[int]) -> str:
        base = (self.base_url or "http://localhost:11434").rstrip("/")
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": max_tokens or self.max_tokens},
        }
        try:
            r = httpx.post(base + "/api/chat", json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json()["message"]["content"]
        except Exception as e:
            raise LLMError(f"Ollama LLM call failed ({base}): {e}") from e

    @staticmethod
    def _mock_response(messages: List[Dict[str, str]]) -> str:
        """Deterministic reply so the offline pipeline stays testable."""
        last = messages[-1]["content"].lower() if messages else ""
        if "tool" in last:
            return json.dumps({"think": "Inspect the flagged flow.",
                               "tool": "explain_flow", "args": {}})
        return "Mock LLM summary: deterministic offline response."

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """Parse a JSON object from an LLM reply that may be fenced or padded."""
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.find("{"):]
        start, end = text.find("{"), text.rfind("}")
        if start == -1:
            raise LLMError(f"No JSON object in LLM reply: {text[:200]!r}")
        candidate = text[start:] if end <= start else text[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = LLMClient._repair_truncated_json(candidate)
            if repaired is not None:
                return repaired
            raise LLMError(f"Malformed JSON from LLM: {candidate[:200]!r}")

    @staticmethod
    def _repair_truncated_json(text: str) -> Optional[Dict[str, Any]]:
        """Close an object truncated mid-value by cutting back to the last
        completed top-level key/value pair and appending the closing brace."""
        if not text.lstrip().startswith("{"):
            return None
        start = text.find("{")
        obj_depth = 0  # depth relative to the outer object's '{'
        in_str = False
        esc = False
        last_top_complete = -1
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch in "{[":
                obj_depth += 1
            elif ch in "]}":
                obj_depth -= 1
                if obj_depth < 0:
                    return None
                if obj_depth == 1:
                    last_top_complete = i + 1
            elif ch == "," and obj_depth == 1:
                last_top_complete = i  # cut before the dangling pair
        if obj_depth >= 1:
            if obj_depth == 1 and not in_str:
                try:
                    return json.loads(text + "}")
                except json.JSONDecodeError:
                    pass
            if last_top_complete > start:
                fragment = text[:last_top_complete].rstrip().rstrip(",")
                try:
                    return json.loads(fragment + "}")
                except json.JSONDecodeError:
                    return None
        return None


_llm: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm

"""Gemini client: Decision 1 for routing choices, a Flash model for JSON extraction. Every call
goes through the Recorder like TinyFish calls, so replays need no key.

REST shapes from ai.google.dev/gemini-api/docs/decisions-api and the generateContent API
(read Nov 21, 2026).
"""

import json
from typing import Any

import httpx
from pydantic import BaseModel

from app.tfclient.recorder import Recorder

API = "https://generativelanguage.googleapis.com/v1beta"
DECISION_MODEL = "gemini-decision-1"


class Choice(BaseModel):
    choice: str
    probabilities: dict[str, float]
    confidence: float


class GeminiClient:
    def __init__(
        self, recorder: Recorder, http: httpx.AsyncClient, api_key: str, flash_model: str
    ) -> None:
        self.recorder = recorder
        self._http = http
        self._headers = {"x-goog-api-key": api_key}
        self.flash_model = flash_model

    async def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        r = await self._http.post(url, json=body, headers=self._headers, timeout=120.0)
        r.raise_for_status()
        return r.json()

    async def choose(self, text: str, question: str, options: dict[str, str]) -> Choice:
        """One Decision 1 choice question over `text`; options map key -> description."""
        request = {
            "model": DECISION_MODEL,
            "input": text,
            "questions": {"q": {"type": "choice", "instructions": question, "criteria": options}},
        }

        async def live() -> dict[str, Any]:
            return await self._post(f"{API}/decisions", request)

        body, _ = await self.recorder.call("gemini", request, live)
        return Choice.model_validate(body["answers"]["q"])

    async def extract_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
        enforce_schema: bool = True,
    ) -> dict[str, Any]:
        """Flash in JSON mode; returns the parsed JSON object. enforce_schema=False puts the schema
        in the prompt instead of responseSchema: Gemini refuses large schemas (the TinyAgent motor
        schema) with HTTP 400 "too many states", and callers validate the output anyway."""
        config: dict[str, Any] = {
            "temperature": temperature,
            "responseMimeType": "application/json",
        }
        if enforce_schema:
            config["responseSchema"] = schema
        else:
            prompt += f"\n\nReturn one JSON object matching this JSON Schema:\n{json.dumps(schema)}"
        request = {
            "model": self.flash_model,
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": config,
        }

        async def live() -> dict[str, Any]:
            body = {k: v for k, v in request.items() if k != "model"}
            return await self._post(f"{API}/models/{self.flash_model}:generateContent", body)

        body, _ = await self.recorder.call("gemini", request, live)
        return json.loads(body["candidates"][0]["content"]["parts"][0]["text"])

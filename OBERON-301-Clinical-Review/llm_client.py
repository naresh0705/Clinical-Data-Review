import json
import re
import time
from abc import ABC, abstractmethod

import config


class LLMClient(ABC):
    @abstractmethod
    def chat(self, user_prompt: str, system_prompt: str = "You are a senior clinical data reviewer.",
             max_tokens: int = 2000, temperature: float = 0.1) -> str: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...


class ClaudeClient(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def chat(self, user_prompt, system_prompt="You are a senior clinical data reviewer.",
             max_tokens=2000, temperature=0.1):
        response = self.client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text

    @property
    def provider_name(self):
        return "claude"

    @property
    def model_name(self):
        return self._model


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self._model = model

    def chat(self, user_prompt, system_prompt="You are a senior clinical data reviewer.",
             max_tokens=2000, temperature=0.1):
        response = self.client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    @property
    def provider_name(self):
        return "openai"

    @property
    def model_name(self):
        return self._model


def create_llm_client(provider: str | None = None) -> LLMClient:
    provider = provider or config.LLM_PROVIDER
    if provider == "claude":
        if not config.CLAUDE_API_KEY:
            raise ValueError("CLAUDE_API_KEY not set in environment")
        return ClaudeClient(api_key=config.CLAUDE_API_KEY, model=config.CLAUDE_MODEL)
    elif provider == "openai":
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment")
        return OpenAIClient(api_key=config.OPENAI_API_KEY, model=config.OPENAI_MODEL)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def parse_llm_json(text: str) -> dict | list:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()

    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    return json.loads(text)

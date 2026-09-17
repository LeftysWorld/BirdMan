"""Gemini image generation: the client and one call. Nothing here knows about birds,
prompts or where images are stored."""
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from birdman.config import ENV_FILE, GEMINI_MODEL


class MissingApiKey(RuntimeError):
    """GOOGLE_API_KEY is not set in .env"""


class GeminiImages:
    """An image generator. Creating one is free and never fails; the API key is only read,
    and the client only built, on the first call to generate()."""

    def __init__(self, model: str = GEMINI_MODEL):
        self.model = model
        self._client = None

    def _connect(self):
        if self._client is None:
            load_dotenv(ENV_FILE)
            key = os.environ.get("GOOGLE_API_KEY")
            if not key:
                raise MissingApiKey(f"GOOGLE_API_KEY is not set in {ENV_FILE}")
            self._client = genai.Client(api_key=key)
        return self._client

    def generate(self, prompt: str, references: list | None = None,
                 aspect_ratio: str | None = None) -> bytes | None:
        """Send a prompt (plus optional reference images) and return the image bytes.

        Returns None if the model answered without an image. A missing key, network, quota
        and API errors are raised - the caller decides what a failure means.
        """
        resp = self._connect().models.generate_content(
            model=self.model,
            contents=[prompt, *references] if references else prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio) if aspect_ratio else None,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data:
                return part.inline_data.data
        return None

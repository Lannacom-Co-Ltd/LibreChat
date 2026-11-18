"""AI image generation and editing.

With an OpenRouter key (IMAGE_BASE_URL https://openrouter.ai/api/v1) every model goes through
OpenRouter's image API (POST /images). Portkey has no /images route and does not forward image
generation for OpenRouter, so behind Portkey the tool falls back to a chat completion that asks
for an image, which only the Gemini image models (Nano Banana) answer.
"""

import base64
import io
import json
import os

import httpx
from PIL import Image

import storage

API_KEY = os.environ.get("IMAGE_API_KEY", "")
BASE_URL = (os.environ.get("IMAGE_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
DEFAULT_MODELS = (
    "openai/gpt-image-2,x-ai/grok-imagine-image-2.0,google/gemini-3.1-flash-image,"
    "google/gemini-3-pro-image,microsoft/mai-image-2.5"
)
MODELS = [m.strip() for m in (os.environ.get("IMAGE_MODELS") or DEFAULT_MODELS).split(",") if m.strip()]
TIMEOUT = float(os.environ.get("IMAGE_TIMEOUT_SECONDS") or "170")
MAX_SOURCE_BYTES = 20 * 1024 * 1024


def headers() -> dict[str, str]:
    extra = json.loads(os.environ.get("IMAGE_HEADERS") or "{}")
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json", **extra}


def source_image(link: str) -> str:
    """A picture to edit, as a data URL. Only files in this server's own store are accepted, so
    the tool cannot be used to fetch arbitrary URLs."""
    key = storage.own_key(link.strip())
    if not key:
        raise ValueError(
            "edit_image_link must be a link returned by create_image (or another file link from "
            "this server); pictures from elsewhere cannot be edited"
        )
    data, content_type = storage.read(key)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("the picture to edit is larger than 20 MB")
    if not content_type.startswith("image/"):
        raise ValueError("edit_image_link does not point to a picture")
    return f"data:{content_type};base64,{base64.b64encode(data).decode()}"


def generate(model: str, prompt: str, aspect_ratio: str, edit_image_link: str | None) -> tuple[bytes, float | None]:
    """Returns (png bytes, cost in USD when the API reports it)."""
    if not API_KEY:
        raise ValueError("image generation is not configured on this server")
    if model not in MODELS:
        raise ValueError(f"model must be one of: {', '.join(MODELS)}")
    source = source_image(edit_image_link) if edit_image_link else None
    payload = post("/images", images_body(model, prompt, aspect_ratio, source), model, allow_missing=True)
    if payload is None:
        payload = post("/chat/completions", chat_body(model, prompt, aspect_ratio, source), model)
    raw = first_image(payload)
    if raw is None:
        raise RuntimeError(f"{model} returned no picture; rephrase the prompt or try another model")
    buf = io.BytesIO()
    Image.open(io.BytesIO(raw)).save(buf, format="PNG", optimize=True)
    return buf.getvalue(), (payload.get("usage") or {}).get("cost")


def images_body(model: str, prompt: str, aspect_ratio: str, source: str | None) -> dict:
    body = {"model": model, "prompt": prompt, "aspect_ratio": aspect_ratio, "n": 1}
    if source:
        body["input_references"] = [{"type": "image_url", "image_url": {"url": source}}]
    return body


def chat_body(model: str, prompt: str, aspect_ratio: str, source: str | None) -> dict:
    """For a gateway without the /images API (Portkey): only models that answer a chat with a
    picture work this way (the Gemini image models)."""
    content = [{"type": "text", "text": prompt}]
    if source:
        content.append({"type": "image_url", "image_url": {"url": source}})
    return {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["image", "text"],
        "image_config": {"aspect_ratio": aspect_ratio},
    }


def post(path: str, body: dict, model: str, allow_missing=False) -> dict | None:
    """The JSON reply, or None when allow_missing and the gateway has no such route."""
    response = httpx.post(f"{BASE_URL}{path}", headers=headers(), json=body, timeout=TIMEOUT)
    if allow_missing and response.status_code in (404, 405):
        return None
    is_json = response.headers.get("content-type", "").startswith("application/json")
    payload = response.json() if is_json else {}
    if response.status_code >= 400 or "error" in payload:
        message = str((payload.get("error") or {}).get("message") or payload.get("message") or response.text)[:400]
        if "not allowed" in message:
            raise ValueError(
                f"{model} is not enabled on the gateway. Try another model, or tell the user an "
                "administrator must enable it."
            )
        if "/api/v1/images" in message or "chat/completions endpoint" in message:
            raise ValueError(
                f"{model} cannot be reached through this gateway. Try a Gemini image model, or tell "
                "the user an administrator must set up direct image access."
            )
        raise RuntimeError(f"{model}: {message}")
    return payload


def first_image(payload: dict) -> bytes | None:
    for item in payload.get("data") or []:
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
    message = (payload.get("choices") or [{}])[0].get("message") or {}
    for image in message.get("images") or []:
        url = (image.get("image_url") or {}).get("url", "")
        if url.startswith("data:image/") and "," in url:
            return base64.b64decode(url.split(",", 1)[1])
    return None

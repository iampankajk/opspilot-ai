"""Translate one bounded findings attempt to the OpenAI Responses API."""

import json
import logging
import os
import re
from http.cookiejar import CookieJar, DefaultCookiePolicy
from typing import Never

from httpx2 import Request, Response
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    DefaultAsyncHttpx2Client,
)
from openai.types.responses import (
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseReasoningItem,
)
from pydantic import SecretStr, ValidationError

from app.findings_provider import InputCount, ProviderFailure, ProviderResult, ProviderStatus
from app.findings_schemas import ProviderName

MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
RESPONSE_ID = re.compile(r"resp_[A-Za-z0-9_-]{1,251}")
_DUPLICATE_JSON_FIELD = object()


async def strip_cookie_headers(request: Request) -> None:
    request.headers.pop("cookie", None)
    request.headers.pop("cookie2", None)


def build_openai_provider(api_key: SecretStr | None) -> "OpenAIFindingsProvider | None":
    key = api_key.get_secret_value() if api_key is not None else ""
    # The SDK otherwise merges ambient headers, which can override auth or send cookies.
    if not key or any(not "!" <= char <= "~" for char in key) or os.getenv("OPENAI_CUSTOM_HEADERS"):
        return None
    # SDK and transport debug logging can include request data or response headers.
    for name in ("openai", "httpx2", "httpcore2"):
        logging.getLogger(name).setLevel(logging.WARNING)
    return OpenAIFindingsProvider(
        AsyncOpenAI(
            api_key=key,
            admin_api_key="",
            webhook_secret="",
            base_url="https://api.openai.com/v1",
            max_retries=0,
            http_client=DefaultAsyncHttpx2Client(
                trust_env=False,
                follow_redirects=False,
                # Reject Set-Cookie at ingestion, including when requests overlap.
                cookies=CookieJar(policy=DefaultCookiePolicy(allowed_domains=())),
                event_hooks={"request": [strip_cookie_headers]},
            ),
        )
    )


def common_request(bundle: dict) -> dict:
    options = bundle["response_options"]
    data = json.dumps(
        {"context": bundle["context"], "evidence": bundle["evidence"]}, sort_keys=True
    )
    return {
        **{key: options[key] for key in ("model", "text", "tools", "truncation", "reasoning")},
        "instructions": bundle["instructions"],
        "input": [{"role": "user", "content": f"Selected synthetic case evidence (JSON):\n{data}"}],
    }


async def send(request):
    try:
        return await request
    except APITimeoutError:
        raise TimeoutError from None
    except APIConnectionError:
        raise ProviderFailure("connection") from None
    except APIStatusError as exc:
        if exc.status_code == 408:
            raise TimeoutError from None
        if exc.status_code == 429:
            raise ProviderFailure("rate_limit") from None
        if 400 <= exc.status_code < 500 and exc.status_code != 409:
            raise ProviderFailure("configuration") from None
        raise ProviderFailure("unavailable") from None
    except (APIResponseValidationError, ValueError, TypeError):
        raise ProviderFailure("invalid") from None


def is_token_count(value: object) -> bool:
    return type(value) is int and 0 <= value <= 2_147_483_647


def mark_duplicate_json_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    # Keep each duplicate at its original location without choosing either value.
    fields = {}
    for key, value in pairs:
        fields[key] = _DUPLICATE_JSON_FIELD if key in fields else value
    return fields


def has_duplicate_json_field(value: object) -> bool:
    pending = [value]
    while pending:
        item = pending.pop()
        if item is _DUPLICATE_JSON_FIELD:
            return True
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return False


def reject_non_json_constant(_: str) -> Never:
    raise ValueError("Invalid JSON numeric literal")


def decode_response_object(response: Response, discriminator: str) -> dict[str, object]:
    # Decode the wire body before SDK parsing can collapse duplicate keys or coerce values.
    try:
        body = response.json(
            object_pairs_hook=mark_duplicate_json_fields, parse_constant=reject_non_json_constant
        )
    except (ValueError, RecursionError):
        raise ProviderFailure("invalid") from None
    if not isinstance(body, dict) or body.get("object") != discriminator:
        raise ProviderFailure("invalid")
    return body


def usage_counters(usage: object) -> dict[str, int] | None:
    if not isinstance(usage, dict) or has_duplicate_json_field(usage):
        return None

    input_details = usage.get("input_tokens_details", {})
    output_details = usage.get("output_tokens_details", {})
    if not isinstance(input_details, dict) or not isinstance(output_details, dict):
        return None

    counters = {key: usage.get(key) for key in ("input_tokens", "output_tokens", "total_tokens")}
    if "cached_tokens" in input_details:
        counters["cached_input_tokens"] = input_details["cached_tokens"]
    if "cache_write_tokens" in input_details:
        counters["cache_write_tokens"] = input_details["cache_write_tokens"]
    if "reasoning_tokens" in output_details:
        counters["reasoning_tokens"] = output_details["reasoning_tokens"]
    if not all(is_token_count(value) for value in counters.values()):
        return None

    input_tokens, output_tokens = counters["input_tokens"], counters["output_tokens"]
    if (
        input_tokens + output_tokens != counters["total_tokens"]
        or counters.get("cached_input_tokens", 0) + counters.get("cache_write_tokens", 0)
        > input_tokens
        or counters.get("reasoning_tokens", 0) > output_tokens
    ):
        return None

    write_details = input_details.get("cache_write_tokens_details")
    if write_details is not None:
        if not isinstance(write_details, dict):
            return None
        short, long = write_details.get("ttl_30m_tokens"), write_details.get("ttl_12h_tokens")
        if (
            not is_token_count(short)
            or not is_token_count(long)
            or short + long != counters.get("cache_write_tokens")
        ):
            return None
    return counters


def response_text(response: dict) -> tuple[ProviderStatus, str]:
    status = response.get("status")
    if not isinstance(status, str):
        return "invalid", ""
    if status == "failed":
        return "failed", ""
    if response.get("error") is not None:
        return "invalid", ""
    if response.get("incomplete_details") is not None:
        return ("incomplete" if status == "incomplete" else "invalid"), ""
    if status in {"incomplete", "queued", "in_progress", "cancelled"}:
        return "incomplete", ""
    items = response.get("output")
    if status != "completed" or not isinstance(items, list):
        return "invalid", ""

    text = []
    refused = False
    try:
        for item in items:
            if not isinstance(item, dict):
                return "invalid", ""
            if item.get("type") == "reasoning":
                reasoning = ResponseReasoningItem.model_validate(item, strict=True)
                if not reasoning.id or reasoning.status not in (None, "completed"):
                    return "invalid", ""
                continue
            if item.get("type") != "message":
                # This request has no tools or other non-message output enabled.
                return "invalid", ""
            message = ResponseOutputMessage.model_validate(item, strict=True)
            if not message.id or message.status != "completed":
                return "invalid", ""
            for part in message.content:
                if isinstance(part, ResponseOutputRefusal):
                    refused = True
                else:
                    text.append(part.text)
    except ValidationError:
        return "invalid", ""

    if refused:
        return "refused", ""
    if len(text) != 1:
        return "invalid", ""
    return "completed", text[0]


class OpenAIFindingsProvider:
    name: ProviderName = "openai"

    def __init__(self, client: AsyncOpenAI):
        self.client = client

    async def close(self) -> None:
        await self.client.close()

    async def count_input(self, bundle: dict, *, timeout: float) -> InputCount:
        raw = await send(
            self.client.responses.input_tokens.with_raw_response.count(
                **common_request(bundle), timeout=timeout
            )
        )
        response = decode_response_object(raw.http_response, "response.input_tokens")
        count = response.get("input_tokens")
        if has_duplicate_json_field(response) or not is_token_count(count):
            raise ProviderFailure("invalid")
        return InputCount(count, "openai_input_tokens")

    async def generate(self, bundle: dict, *, timeout: float) -> ProviderResult:
        options = bundle["response_options"] | common_request(bundle)
        raw = await send(self.client.responses.with_raw_response.create(**options, timeout=timeout))
        response = decode_response_object(raw.http_response, "response")
        if any(
            has_duplicate_json_field(value) for key, value in response.items() if key != "usage"
        ):
            raise ProviderFailure("invalid")

        model = response.get("model")
        response_id = response.get("id")
        if not isinstance(model, str) or not MODEL_ID.fullmatch(model):
            raise ProviderFailure("invalid")
        if model != options["model"]:
            raise ProviderFailure("configuration")
        if not isinstance(response_id, str) or not RESPONSE_ID.fullmatch(response_id):
            raise ProviderFailure("invalid")

        status, output_json = response_text(response)
        if status == "invalid":
            raise ProviderFailure("invalid")
        return ProviderResult(
            output_json=output_json if status == "completed" else "",
            status=status,
            model=model,
            response_id=response_id,
            usage=usage_counters(response.get("usage")),
            standard_tier=response.get("service_tier") == "default",
        )

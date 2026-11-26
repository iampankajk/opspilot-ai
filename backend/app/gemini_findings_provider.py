"""Gemini Developer API wire contract for findings, with one count and one generation."""

import contextlib
import json
import logging
import re
from http.cookiejar import CookieJar, DefaultCookiePolicy

import httpx2
from google import genai
from google.genai import errors, types
from google.genai.client import DebugConfig
from pydantic import SecretStr

from app.config import GEMINI_FINDINGS_MODEL
from app.findings_provider import (
    InputCount,
    ProviderFailure,
    ProviderResult,
    ProviderStatus,
    evidence_message,
    has_duplicate_json_field,
    is_token_count,
    mark_duplicate_json_fields,
    reject_non_json_constant,
)
from app.findings_schemas import FindingGenerationOutput, FindingsProviderJsonSchema, ProviderName

API_ORIGIN = "https://generativelanguage.googleapis.com"
MODEL_PATH = f"/v1/models/{GEMINI_FINDINGS_MODEL}"
API_KEY = re.compile(r"[!-~]{1,256}")
RESPONSE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
BLOCKED_PROMPTS = {"SAFETY", "OTHER", "BLOCKLIST", "PROHIBITED_CONTENT", "IMAGE_SAFETY"}
REFUSAL_REASONS = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}
RETRY_OPTIONS = types.HttpRetryOptions(attempts=1)
MAX_ERROR_BODY_BYTES = 65536
UPSTREAM_ERROR_STATUSES = frozenset(
    {
        "ABORTED",
        "ALREADY_EXISTS",
        "CANCELLED",
        "DATA_LOSS",
        "DEADLINE_EXCEEDED",
        "FAILED_PRECONDITION",
        "INTERNAL",
        "INVALID_ARGUMENT",
        "NOT_FOUND",
        "OUT_OF_RANGE",
        "PERMISSION_DENIED",
        "RESOURCE_EXHAUSTED",
        "UNAUTHENTICATED",
        "UNAVAILABLE",
        "UNIMPLEMENTED",
        "UNKNOWN",
    }
)
logger = logging.getLogger(__name__)


class GeminiFindingsJsonSchema(FindingsProviderJsonSchema):
    """Project supported constraints onto the wire while keeping strict application validation."""

    def str_schema(self, schema):
        result = super().str_schema(schema)
        result.pop("pattern", None)
        return result

    def literal_schema(self, schema):
        result = super().literal_schema(schema)
        if "const" in result:
            result["enum"] = [result.pop("const")]
        return result

    def int_schema(self, schema):
        result = super().int_schema(schema)
        if "exclusiveMaximum" in result:
            result["maximum"] = result.pop("exclusiveMaximum") - 1
        return result


def gemini_response_options(max_output_tokens: int) -> dict:
    return {
        "model": GEMINI_FINDINGS_MODEL,
        "generationConfig": {
            "candidateCount": 1,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
            "responseJsonSchema": FindingGenerationOutput.model_json_schema(
                schema_generator=GeminiFindingsJsonSchema
            ),
            "thinkingConfig": {"thinkingLevel": "MINIMAL"},
        },
    }


def generation_request(bundle: dict) -> dict:
    return {
        "model": f"models/{bundle['response_options']['model']}",
        "contents": [{"role": "user", "parts": [{"text": evidence_message(bundle)}]}],
        "systemInstruction": {"parts": [{"text": bundle["instructions"]}]},
        "generationConfig": bundle["response_options"]["generationConfig"],
    }


def response_request(response: httpx2.Response) -> httpx2.Request | None:
    try:
        return response.request
    except RuntimeError:
        return None


def request_operation(request: httpx2.Request | None) -> str:
    if request is None:
        return "unknown"
    path = request.url.path
    if path == f"{MODEL_PATH}:countTokens":
        return "count_tokens"
    if path == f"{MODEL_PATH}:generateContent":
        return "generate_content"
    return "unknown"


async def read_bounded_error_bytes(response: httpx2.Response) -> bytes | None:
    try:
        if response.is_stream_consumed:
            return response.content if len(response.content) <= MAX_ERROR_BODY_BYTES else None
        chunks = bytearray()
        async with contextlib.aclosing(response.aiter_bytes()) as stream:
            async for chunk in stream:
                if len(chunks) + len(chunk) > MAX_ERROR_BODY_BYTES:
                    return None
                chunks.extend(chunk)
        return bytes(chunks)
    finally:
        try:
            await response.aclose()
        except (httpx2.HTTPError, httpx2.StreamError):
            pass


async def extract_upstream_error_status(response: httpx2.Response) -> str | None:
    try:
        raw_bytes = await read_bounded_error_bytes(response)
        if raw_bytes is None:
            return None
        text = raw_bytes.decode("utf-8", errors="strict")
        payload = json.loads(
            text,
            object_pairs_hook=mark_duplicate_json_fields,
            parse_constant=reject_non_json_constant,
        )
    except (
        UnicodeDecodeError,
        ValueError,
        RecursionError,
        httpx2.HTTPError,
        httpx2.StreamError,
    ):
        return None
    if not isinstance(payload, dict) or has_duplicate_json_field(payload):
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    status = error.get("status")
    if type(status) is str and status in UPSTREAM_ERROR_STATUSES:
        return status
    return None


async def log_upstream_http_error(response: httpx2.Response) -> None:
    operation = request_operation(response_request(response))
    status_code = response.status_code
    http_status = status_code if type(status_code) is int and 100 <= status_code <= 599 else None
    upstream_status = await extract_upstream_error_status(response)
    fields = ["category=upstream_http_error", f"operation={operation}"]
    if http_status is not None:
        fields.append(f"http_status={http_status}")
    if upstream_status is not None:
        fields.append(f"upstream_error_status={upstream_status}")
    logger.warning("Gemini diagnostic: %s", " ".join(fields))


async def guard_request(request: httpx2.Request) -> None:
    if request.method != "POST" or str(request.url) not in {
        f"{API_ORIGIN}{MODEL_PATH}:countTokens",
        f"{API_ORIGIN}{MODEL_PATH}:generateContent",
    }:
        reason = "unexpected_method" if request.method != "POST" else "unexpected_url"
        logger.warning(
            "Gemini diagnostic: category=local_request_guard reason=%s",
            reason,
        )
        raise ProviderFailure("configuration")
    request.headers.pop("cookie", None)
    request.headers.pop("cookie2", None)


async def validate_response_encoding(response: httpx2.Response) -> None:
    if response.status_code != 200:
        await log_upstream_http_error(response)
        # Classify HTTP errors before the SDK reads or JSON-decodes an untrusted error body.
        raise http_failure(response.status_code)
    # The SDK's raw result holds text. Check the original bytes before it reads response.text.
    body = await response.aread()
    try:
        body.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ProviderFailure("invalid") from None
    response.encoding = "utf-8"


async def build_gemini_provider(api_key: SecretStr | None) -> "GeminiFindingsProvider | None":
    key = api_key.get_secret_value() if api_key is not None else ""
    if not API_KEY.fullmatch(key):
        return None
    for name in ("google_genai", "httpx2", "httpcore2"):
        logging.getLogger(name).setLevel(logging.WARNING)
    transport = httpx2.AsyncClient(
        trust_env=False,
        follow_redirects=False,
        transport=httpx2.AsyncHTTPTransport(retries=0, trust_env=False),
        cookies=CookieJar(policy=DefaultCookiePolicy(allowed_domains=())),
        event_hooks={"request": [guard_request], "response": [validate_response_encoding]},
    )
    try:
        client = genai.Client(
            enterprise=False,
            api_key=key,
            # Every DebugConfig default can come from the environment.
            debug_config=DebugConfig(client_mode=None, replays_directory=None, replay_id=None),
            http_options=types.HttpOptions(
                base_url=API_ORIGIN,
                api_version="v1",
                retry_options=RETRY_OPTIONS,
                httpx_async_client=transport,
                client_args={"trust_env": False, "follow_redirects": False},
            ),
        )
    except (TypeError, ValueError):
        await transport.aclose()
        return None
    return GeminiFindingsProvider(client, transport, key)


def http_failure(status: int) -> Exception:
    if status in {408, 504}:
        return TimeoutError()
    if status == 429:
        return ProviderFailure("rate_limit")
    if 400 <= status < 500 and status != 409:
        return ProviderFailure("configuration")
    return ProviderFailure("unavailable")


async def send(call):
    try:
        return await call
    except httpx2.TimeoutException:
        raise TimeoutError from None
    except httpx2.RequestError:
        raise ProviderFailure("connection") from None
    except errors.APIError as exc:
        raise http_failure(exc.code) from None
    except (ValueError, TypeError, RecursionError):
        raise ProviderFailure("invalid") from None


def decode_response(body: str) -> dict:
    if len(body) > 262144:
        raise ProviderFailure("invalid")
    try:
        response = json.loads(
            body,
            object_pairs_hook=mark_duplicate_json_fields,
            parse_constant=reject_non_json_constant,
        )
    except (ValueError, RecursionError):
        raise ProviderFailure("invalid") from None
    if not isinstance(response, dict) or "error" in response:
        raise ProviderFailure("invalid")
    return response


def usage_counters(usage: object, *, completed: bool) -> dict[str, int] | None:
    if not isinstance(usage, dict) or has_duplicate_json_field(usage):
        return None
    prompt = usage.get("promptTokenCount")
    total = usage.get("totalTokenCount")
    candidates = usage.get("candidatesTokenCount", None if completed else 0)
    thoughts = usage.get("thoughtsTokenCount", 0)
    cached = usage.get("cachedContentTokenCount", 0)
    tool_use = usage.get("toolUsePromptTokenCount", 0)
    if not all(
        is_token_count(value) for value in (prompt, total, candidates, thoughts, cached, tool_use)
    ):
        return None
    if cached > prompt or tool_use or prompt + candidates + thoughts != total:
        return None
    counters = {
        "input_tokens": prompt,
        "output_tokens": candidates + thoughts,
        "total_tokens": total,
    }
    if "cachedContentTokenCount" in usage:
        counters["cached_input_tokens"] = cached
    if "thoughtsTokenCount" in usage:
        counters["reasoning_tokens"] = thoughts
    return counters


def response_text(response: dict) -> tuple[ProviderStatus, str]:
    feedback = response.get("promptFeedback", {})
    if not isinstance(feedback, dict):
        raise ProviderFailure("invalid")
    block = feedback.get("blockReason", "BLOCK_REASON_UNSPECIFIED")
    candidates = response.get("candidates", [])
    if not isinstance(block, str) or not isinstance(candidates, list):
        raise ProviderFailure("invalid")
    if block in BLOCKED_PROMPTS and not candidates:
        return "refused", ""
    if block != "BLOCK_REASON_UNSPECIFIED" or len(candidates) != 1:
        raise ProviderFailure("invalid")
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        raise ProviderFailure("invalid")
    index = candidate.get("index", 0)
    finish = candidate.get("finishReason")
    if type(index) is not int or index != 0 or not isinstance(finish, str):
        raise ProviderFailure("invalid")
    continuation_token = candidate.get("continuationToken")
    if continuation_token is not None and (
        finish != "CONTINUATION" or not isinstance(continuation_token, str)
    ):
        raise ProviderFailure("invalid")
    status: ProviderStatus
    if finish in REFUSAL_REASONS:
        status = "refused"
    elif finish in {"MAX_TOKENS", "CONTINUATION"}:
        status = "incomplete"
    elif finish == "STOP":
        status = "completed"
    else:
        raise ProviderFailure("invalid")

    content = candidate.get("content", {})
    if not isinstance(content, dict) or content.get("role", "model") != "model":
        raise ProviderFailure("invalid")
    parts = content.get("parts", [])
    if not isinstance(parts, list):
        raise ProviderFailure("invalid")
    text = []
    for part in parts:
        if not isinstance(part, dict) or part.keys() - {"text", "thought", "thoughtSignature"}:
            raise ProviderFailure("invalid")
        thought = part.get("thought", False)
        signature = part.get("thoughtSignature", "")
        value = part.get("text")
        if type(thought) is not bool or not isinstance(signature, str):
            raise ProviderFailure("invalid")
        if signature and "text" not in part:
            continue
        if not isinstance(value, str):
            raise ProviderFailure("invalid")
        if not thought:
            if status == "completed" and not value:
                raise ProviderFailure("invalid")
            text.append(value)
    if status != "completed":
        return status, ""
    output = "".join(text)
    if not output.strip():
        raise ProviderFailure("invalid")
    return "completed", output


class GeminiFindingsProvider:
    name: ProviderName = "gemini"

    def __init__(self, client: genai.Client, transport: httpx2.AsyncClient, key: str):
        self.client = client
        self.transport = transport
        self._key = SecretStr(key)

    async def close(self) -> None:
        try:
            await self.client.aio.aclose()
        finally:
            try:
                await self.transport.aclose()
            finally:
                self.client.close()

    async def count_input(self, bundle: dict, *, timeout: float) -> InputCount:
        response = await send(
            self.transport.post(
                f"{API_ORIGIN}{MODEL_PATH}:countTokens",
                headers={"x-goog-api-key": self._key.get_secret_value()},
                json={"generateContentRequest": generation_request(bundle)},
                timeout=timeout,
            )
        )
        if response.status_code != 200:
            raise http_failure(response.status_code)
        body = decode_response(response.text)
        count = body.get("totalTokens")
        if has_duplicate_json_field(body) or not is_token_count(count) or count == 0:
            raise ProviderFailure("invalid")
        return InputCount(count, "gemini_count_tokens")

    async def generate(self, bundle: dict, *, timeout: float) -> ProviderResult:
        request = generation_request(bundle)
        generation_config = request["generationConfig"].copy()
        thinking = generation_config.pop("thinkingConfig")
        config = types.GenerateContentConfig.model_validate(
            generation_config
            | {
                "system_instruction": request["systemInstruction"],
                "automatic_function_calling": {"disable": True},
                "automatic_continuation": False,
                "should_return_http_response": True,
                "http_options": {
                    "timeout": max(1, int(timeout * 1000)),
                    "retry_options": RETRY_OPTIONS,
                    # The pinned SDK serializes ThinkingConfig in snake case. Keep the
                    # exact REST field names used for the nested countTokens request.
                    "extra_body": {"generationConfig": {"thinkingConfig": thinking}},
                },
            }
        )
        raw = await send(
            self.client.aio.models.generate_content(
                model=request["model"], contents=request["contents"], config=config
            )
        )
        body = decode_response(raw.sdk_http_response.body or "")
        if any(
            has_duplicate_json_field(value) for key, value in body.items() if key != "usageMetadata"
        ):
            raise ProviderFailure("invalid")
        status, output = response_text(body)
        model = body.get("modelVersion")
        if model is not None and not isinstance(model, str):
            raise ProviderFailure("invalid")
        if model is not None and model != GEMINI_FINDINGS_MODEL:
            logger.warning(
                "Gemini diagnostic: category=model_version_mismatch "
                "operation=generate_content http_status=200"
            )
            raise ProviderFailure("configuration")
        if status == "completed" and model is None:
            raise ProviderFailure("invalid")
        response_id = body.get("responseId")
        if (
            not isinstance(response_id, str)
            or not RESPONSE_ID.fullmatch(response_id)
            or self._key.get_secret_value() in response_id
        ):
            response_id = None
        return ProviderResult(
            output_json=output,
            status=status,
            model=model,
            response_id=response_id,
            usage=usage_counters(body.get("usageMetadata"), completed=status == "completed"),
        )

"""Provider adapter protocol and deterministic JSON transcript implementation."""

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Protocol, Tuple, runtime_checkable


class TranscriptFormatError(ValueError):
    """Raised when a transcript does not conform to the replay format."""


class ProviderCallError(RuntimeError):
    """A structured error replayed by a transcript provider."""

    def __init__(self, code: str, message: str, details: Mapping[str, Any] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


@runtime_checkable
class ProviderAdapter(Protocol):
    """Minimal boundary between the runner and a tool-server adapter.

    An adapter translates the canonical profile operation names into calls to its
    target.  The assurance package deliberately does not implement MCP transport,
    discovery, authentication, or process management.
    """

    @property
    def name(self) -> str:
        """Return a human-readable provider name."""

    def call(self, operation: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Invoke one canonical assurance operation and return a JSON-like mapping."""


class TranscriptProvider:
    """Replay canonical provider calls from a JSON transcript.

    Duplicate request entries form an ordered response sequence.  Once that
    sequence is exhausted, the final entry is reused.  ``reset`` rewinds all
    sequences, allowing each assurance check to run in isolation.
    """

    SUPPORTED_VERSION = "1.0"

    def __init__(self, transcript: Mapping[str, Any]) -> None:
        self._name = self._validate_name(transcript.get("name", "json-transcript"))
        version = transcript.get("transcript_version")
        if version != self.SUPPORTED_VERSION:
            raise TranscriptFormatError(
                "transcript_version must be {!r}; got {!r}".format(self.SUPPORTED_VERSION, version)
            )
        exchanges = transcript.get("exchanges")
        if not isinstance(exchanges, list) or not exchanges:
            raise TranscriptFormatError("exchanges must be a non-empty array")

        self._entries: Dict[str, List[Tuple[str, Mapping[str, Any]]]] = {}
        for index, exchange in enumerate(exchanges):
            self._add_exchange(index, exchange)
        self._positions: MutableMapping[str, int] = {}

    @classmethod
    def from_file(cls, path: str) -> "TranscriptProvider":
        try:
            with Path(path).open("r", encoding="utf-8") as handle:
                transcript = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise TranscriptFormatError("could not read transcript {!r}: {}".format(path, exc)) from exc
        if not isinstance(transcript, dict):
            raise TranscriptFormatError("transcript root must be an object")
        return cls(transcript)

    @property
    def name(self) -> str:
        return self._name

    def reset(self) -> None:
        self._positions.clear()

    def call(self, operation: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(operation, str) or not operation:
            raise TypeError("operation must be a non-empty string")
        if not isinstance(arguments, Mapping):
            raise TypeError("arguments must be a mapping")
        key = self._signature(operation, arguments)
        entries = self._entries.get(key)
        if not entries:
            raise ProviderCallError(
                "TRANSCRIPT_MISS",
                "no transcript exchange matches the request",
                {"operation": operation, "arguments": copy.deepcopy(dict(arguments))},
            )
        position = self._positions.get(key, 0)
        entry = entries[min(position, len(entries) - 1)]
        self._positions[key] = position + 1
        kind, payload = entry
        copied = copy.deepcopy(dict(payload))
        if kind == "error":
            raise ProviderCallError(
                str(copied.get("code", "PROVIDER_ERROR")),
                str(copied.get("message", "provider call failed")),
                copied.get("details") if isinstance(copied.get("details"), Mapping) else {},
            )
        return copied

    def _add_exchange(self, index: int, exchange: Any) -> None:
        label = "exchanges[{}]".format(index)
        if not isinstance(exchange, dict):
            raise TranscriptFormatError("{} must be an object".format(label))
        request = exchange.get("request")
        if not isinstance(request, dict):
            raise TranscriptFormatError("{}.request must be an object".format(label))
        operation = request.get("operation")
        arguments = request.get("arguments", {})
        if not isinstance(operation, str) or not operation:
            raise TranscriptFormatError("{}.request.operation must be a non-empty string".format(label))
        if not isinstance(arguments, dict):
            raise TranscriptFormatError("{}.request.arguments must be an object".format(label))

        has_response = "response" in exchange
        has_error = "error" in exchange
        if has_response == has_error:
            raise TranscriptFormatError("{} must contain exactly one of response or error".format(label))
        kind = "response" if has_response else "error"
        payload = exchange[kind]
        if not isinstance(payload, dict):
            raise TranscriptFormatError("{}.{} must be an object".format(label, kind))
        if kind == "error":
            if not isinstance(payload.get("code"), str) or not isinstance(payload.get("message"), str):
                raise TranscriptFormatError("{}.error requires string code and message".format(label))

        key = self._signature(operation, arguments)
        self._entries.setdefault(key, []).append((kind, copy.deepcopy(payload)))

    @staticmethod
    def _signature(operation: str, arguments: Mapping[str, Any]) -> str:
        try:
            return json.dumps(
                {"operation": operation, "arguments": dict(arguments)},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise TranscriptFormatError("request is not canonical JSON: {}".format(exc)) from exc

    @staticmethod
    def _validate_name(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise TranscriptFormatError("name must be a non-empty string")
        return value.strip()

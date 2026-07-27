# Core Assurance Profile Specification

Status: MVP, profile ID `core`, transcript version `1.0`.

## 1. Purpose and boundary

The core profile defines black-box probes for a legal/retrieval provider adapter. It verifies observable response contracts. It does not define MCP transport, server discovery, authentication, network behavior, authorization, or legal conclusions.

Passing means that the sampled responses met these assertions. It is not legal advice, a certification, or proof that an underlying corpus is complete or legally authoritative.

## 2. Provider adapter protocol

A provider implements:

```python
@property
def name(self) -> str: ...

def call(
    self,
    operation: str,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]: ...
```

`call` accepts a canonical operation name and JSON-like arguments. It returns a JSON-like object. An adapter translates this vocabulary to its target server. The runner catches adapter exceptions per check and records them as `error` results.

`reset() -> None` is an optional extension. If present, the runner calls it before each check. The transcript provider uses this hook so duplicate exchanges are replayed from the beginning for every isolated check.

All strings in this profile use Unicode. Source span offsets are zero-based, half-open Unicode code-point positions: `[start, end)`. They are directly compatible with Python string slicing for normalized transcript strings. An adapter must account for any byte/code-unit differences in its target.

## 3. Fixed probe values

The MVP profile uses fixed synthetic probes so recorded transcripts remain portable:

| Symbol | Value |
| --- | --- |
| `document_id` | `doc-roe-410-us-113` |
| primary query | `410 U.S. 113` |
| as-of query | `example authority` |
| as-of date | `2000-01-01` |
| missing query | `Imaginary Reporter 999 X.Y. 999` |
| interpretation question | `What is the holding?` |

The identifiers name synthetic fixture data; the profile does not assert a legal proposition about any real authority.

## 4. Canonical operations

The examples below show required fields used by checks. Providers may return additional fields unless a check explicitly requires an exact envelope.

### 4.1 `capabilities.get`

Request:

```json
{}
```

Required response properties:

```json
{
  "read_only": true,
  "mutating_operations": [],
  "schema_version": "1.0"
}
```

`read_only` must be the JSON boolean `true`. `mutating_operations` must be an empty array.

### 4.2 `capabilities.read_only_probe`

Request:

```json
{
  "operation": "create_annotation",
  "mode": "dry-run"
}
```

Required response:

```json
{
  "state": "rejected",
  "code": "READ_ONLY",
  "side_effects": false
}
```

The profile asks only for an adapter-level dry-run assertion. Implementations must not perform a real mutation to satisfy this probe.

### 4.3 `document.get`

Request:

```json
{"document_id": "doc-roe-410-us-113"}
```

Required response properties:

```json
{
  "state": "found",
  "document_id": "doc-roe-410-us-113",
  "content": "...",
  "source_hash": "sha256:<64 lowercase hexadecimal characters>"
}
```

`content` must be non-empty. The hash is SHA-256 over the exact UTF-8 encoding of `content`, with no implicit trimming or newline conversion.

### 4.4 `quote.get`

Request:

```json
{
  "document_id": "doc-roe-410-us-113",
  "selector": "holding"
}
```

Required response properties:

```json
{
  "document_id": "doc-roe-410-us-113",
  "quote": "exact source characters",
  "span": {
    "start": 20,
    "end": 43,
    "unit": "unicode-code-point"
  }
}
```

The numeric values above are illustrative. The assertion is `quote == content[start:end]`, with integer (not boolean) offsets and valid bounds.

### 4.5 `search`

Primary request:

```json
{"query": "410 U.S. 113", "limit": 1}
```

Required top-level fields:

```json
{
  "state": "found",
  "query": "410 U.S. 113",
  "retrieved_at": "2025-01-15T12:00:00Z",
  "results": []
}
```

For the primary probe, at least one result is required. Its relevant fields are:

```json
{
  "document_id": "stable-non-empty-id",
  "citation": {
    "canonical": "410 U.S. 113",
    "display": "non-empty human display form",
    "normalization": "reporter-volume-page"
  },
  "jurisdiction": {
    "code": "non-empty machine code",
    "name": "non-empty display name"
  }
}
```

`retrieved_at` must be an ISO 8601 datetime with an explicit UTC offset or `Z`.

Missing-authority request:

```json
{"query": "Imaginary Reporter 999 X.Y. 999", "limit": 5}
```

Required absence response:

```json
{
  "state": "absent",
  "query": "Imaginary Reporter 999 X.Y. 999",
  "results": [],
  "absence": {
    "code": "NO_MATCH",
    "message": "..."
  }
}
```

An empty successful/found response is not equivalent to explicit absence.

Invalid request:

```json
{"query": 17, "limit": -1}
```

The exact required envelope is:

```json
{
  "state": "error",
  "error": {
    "code": "non-empty string",
    "message": "non-empty string",
    "details": {}
  }
}
```

Top-level keys must be exactly `state` and `error`; error keys must be exactly `code`, `message`, and `details`. Two identical calls must return deeply equal JSON values.

### 4.6 `search.as_of`

Request:

```json
{
  "query": "example authority",
  "as_of": "2000-01-01",
  "limit": 10
}
```

Required response properties:

```json
{
  "state": "found",
  "as_of": "2000-01-01",
  "retrieved_at": "2025-01-15T12:00:00Z",
  "results": [
    {
      "document_id": "...",
      "effective_from": "1995-06-01",
      "effective_to": null
    }
  ]
}
```

`state` may be `found` or `absent`. `as_of` must echo the requested date. For every result, `effective_from <= as_of`; if `effective_to` is non-null, then `effective_to >= as_of`. Dates use ISO calendar form. `retrieved_at` describes when retrieval occurred and remains distinct from legal/effective time.

### 4.7 `corpus.status`

Request:

```json
{}
```

Required response shape:

```json
{
  "coverage": {
    "jurisdictions": ["us-federal"],
    "authority_types": ["reported-decisions"],
    "publication_date_range": {
      "from": "1790-01-01",
      "through": "2025-01-15"
    },
    "exclusions": ["sealed records"]
  },
  "freshness": {
    "snapshot_at": "2025-01-15T00:00:00Z",
    "max_age_days": 30,
    "status": "current",
    "basis": "provider-declared source snapshot"
  }
}
```

Coverage jurisdiction and authority arrays must be non-empty. Exclusions must be an array and may be empty. Range endpoints must be ISO dates with `from <= through`. `snapshot_at` must be timezone-aware; `max_age_days` is a non-negative integer (not boolean); `status` is `current`, `stale`, or `unknown`; `basis` is a non-empty string. The provider makes these declarations; the MVP does not independently crawl a corpus to verify them.

### 4.8 `interpret`

Request:

```json
{
  "document_id": "doc-roe-410-us-113",
  "question": "What is the holding?"
}
```

Relevant response shape:

```json
{
  "state": "completed",
  "segments": [
    {
      "kind": "source_text",
      "text": "exact source characters",
      "span": {"start": 20, "end": 43}
    },
    {
      "kind": "generated_interpretation",
      "label": "Generated interpretation",
      "text": "non-empty generated text"
    }
  ]
}
```

Every segment must use one of the two recognized kinds. At least one of each kind is required. A source segment must exactly round-trip to `document.get` content; a generated segment must carry the exact label `Generated interpretation`.

## 5. Checks

| ID | Name | Failure condition summary |
| --- | --- | --- |
| `LMA-001` | Read-only capability declaration | Declaration is not read-only or the mutating operation list is not empty. |
| `LMA-002` | Read-only mutation rejection | Dry-run mutation is not rejected with `READ_ONLY` and `side_effects=false`. |
| `LMA-003` | Exact quote/source-span round trip | Quote, document ID, integer offsets, bounds, or exact slice differs. |
| `LMA-004` | Stable document identifiers | Two identical searches do not return the same non-empty ID. |
| `LMA-005` | Citation normalization | Canonical/display/method fields are absent or canonical form differs. |
| `LMA-006` | Jurisdiction metadata | Jurisdiction is not structured with non-empty code and name. |
| `LMA-007` | Retrieval timestamp | Timestamp is absent, invalid, or lacks timezone information. |
| `LMA-008` | As-of response contract | As-of echo, state, result array, or retrieval timestamp is invalid. |
| `LMA-009` | Point-in-time effective intervals | A result falls outside its effective interval at the cutoff. |
| `LMA-010` | Source hash declaration | Hash does not use lowercase `sha256:<64 hex>` syntax. |
| `LMA-011` | Source hash integrity | SHA-256 does not match exact returned UTF-8 source text. |
| `LMA-012` | Explicit corpus coverage | Scope arrays, ordered date range, or exclusions are not explicit. |
| `LMA-013` | Explicit corpus freshness | Snapshot, age policy, status, or basis is not explicit. |
| `LMA-014` | Explicit absence state | Missing authority is not represented as `absent` with empty results and `NO_MATCH`. |
| `LMA-015` | Interpretation source fidelity | No source segment exists or an exact source span fails to round-trip. |
| `LMA-016` | Generated interpretation separation | Segments are untyped/mixed or generated interpretation is absent or unlabeled. |
| `LMA-017` | Deterministic response schema | Two identical primary searches produce different recursive JSON type/key schemas or lack required fields. |
| `LMA-018` | Deterministic errors | Two invalid calls differ or do not use the exact structured envelope. |

A check status is:

- `pass`: the assertion held;
- `fail`: the provider returned a usable response that violated the assertion; or
- `error`: the adapter/reset/check boundary raised an exception.

Any `fail` or `error` makes a run unsuccessful and causes CLI exit code `1`.

## 6. Transcript replay

A version `1.0` transcript has this root shape:

```json
{
  "transcript_version": "1.0",
  "name": "provider-name",
  "exchanges": []
}
```

Every exchange contains `request` and exactly one of `response` or `error`:

```json
{
  "request": {"operation": "search", "arguments": {"query": "..."}},
  "response": {"state": "found", "results": []}
}
```

```json
{
  "request": {"operation": "search", "arguments": {"query": "..."}},
  "error": {
    "code": "UPSTREAM_UNAVAILABLE",
    "message": "recorded adapter failure",
    "details": {}
  }
}
```

Matching uses canonical JSON serialization with sorted object keys and rejects non-JSON values. Duplicate request entries create a response sequence. Calls consume that sequence in order; after it is exhausted, its final item is reused. `reset()` rewinds all sequences before the next isolated check. Transcript responses are deep-copied before return so check code cannot mutate stored fixtures.

## 7. Report contract

The JSON report includes tool/profile/provider metadata, UTC start/finish timestamps, a summary, and ordered check results. Each check contains ID, title, requirement, status, message, evidence, and duration milliseconds.

JUnit represents every check as a test case. `fail` becomes `<failure>` and `error` becomes `<error>`. SARIF declares every check as a rule and emits a result only for `fail` or `error`. Durations and run timestamps are observational and are not expected to be byte-for-byte deterministic.

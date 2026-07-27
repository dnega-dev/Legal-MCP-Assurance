# Legal MCP Assurance

Legal MCP Assurance is a zero-runtime-dependency Python 3.9+ black-box assurance runner for adapters in front of legal and retrieval tool servers. It checks observable contracts around provenance, temporal semantics, corpus transparency, explicit absence, generated text separation, and deterministic interfaces.

It **does not implement MCP transport**. A provider adapter is responsible for translating the profile's canonical operations to the target server. The included JSON transcript provider makes runs deterministic and usable offline.

This project evaluates technical response properties. It does not provide legal advice, determine the legal sufficiency of a source, or certify that a system is suitable for a particular use.

## Highlights

- Python standard library only at runtime
- Provider adapter `Protocol` plus deterministic JSON transcript replay
- Eighteen core black-box checks covering:
  - declared read-only behavior and rejected dry-run mutation probes
  - exact quote/source-span round trips
  - stable document IDs
  - normalized citations
  - structured jurisdiction and retrieval timestamps
  - point-in-time/as-of behavior
  - source SHA-256 hashes
  - explicit corpus coverage and freshness
  - explicit absence for missing authority
  - separation of source text from generated interpretation
  - deterministic response schemas and errors
- Text, JSON, JUnit XML, and SARIF 2.1.0 output
- Nonzero exit status for assurance failures and provider errors
- Good and deliberately broken offline transcript examples

## Quick start

From a source checkout:

```sh
PYTHONPATH=src python3 -m legal_mcp_assurance profiles list
PYTHONPATH=src python3 -m legal_mcp_assurance profiles show core
PYTHONPATH=src python3 -m legal_mcp_assurance run \
  --profile core \
  --transcript examples/good-transcript.json \
  --format text
```

Or install the project and use the console script:

```sh
python3 -m pip install .
legal-mcp-assurance run --transcript examples/good-transcript.json
```

Generate a starter transcript:

```sh
legal-mcp-assurance init example my-transcript.json
```

The command refuses to overwrite an existing path unless `--force` is supplied. Add `--broken` to generate a deliberately nonconforming fixture.

## CLI

```text
legal-mcp-assurance run --transcript PATH [--profile core]
                        [--format text|json|junit|sarif] [--output PATH]
legal-mcp-assurance profiles list [--format text|json]
legal-mcp-assurance profiles show PROFILE [--format text|json]
legal-mcp-assurance init example [PATH] [--broken] [--force]
```

Exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | The command completed and all assurance checks passed. |
| `1` | A profile run completed with one or more failures or provider errors. |
| `2` | CLI usage, input, transcript, profile, or output error. |

When `--output` is omitted (or is `-`), reports are written to standard output. Diagnostics are written to standard error.

## Provider adapter boundary

Adapters implement the intentionally small protocol:

```python
from typing import Any, Mapping

class MyAdapter:
    @property
    def name(self) -> str:
        return "my-provider"

    def call(self, operation: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        # Translate the canonical profile operation to the target server.
        # Transport, credentials, and process lifecycle belong here.
        ...
```

Run an in-process adapter with:

```python
from legal_mcp_assurance import AssuranceRunner, get_profile

result = AssuranceRunner().run(get_profile("core"), MyAdapter())
print(result.summary())
```

An adapter may additionally implement `reset()`. The runner invokes it before each check, which is useful for deterministic replay fixtures; it is not required by `ProviderAdapter`.

See [`docs/profile-spec.md`](docs/profile-spec.md) for canonical operations, field semantics, transcript sequencing, and check IDs.

## Transcript format

A transcript is a JSON object with a version, provider name, and request/response exchanges:

```json
{
  "transcript_version": "1.0",
  "name": "example-provider",
  "exchanges": [
    {
      "request": {"operation": "capabilities.get", "arguments": {}},
      "response": {
        "read_only": true,
        "mutating_operations": [],
        "schema_version": "1.0"
      }
    }
  ]
}
```

Requests are matched by canonical JSON value, not object key order. Duplicate matching exchanges are replayed in order and the final response is reused after the sequence is exhausted. Each profile check begins from the start of the sequence. An exchange may use an `error` object instead of `response` to simulate an adapter exception; an assurance run records that as a check error rather than crashing the suite.

## Reports

- **text**: concise human-readable check list and summary
- **json**: complete stable report object for automation
- **junit**: one test case per assurance check, suitable for CI test viewers
- **sarif**: rules for all checks and findings for failures/errors

Examples:

```sh
PYTHONPATH=src python3 -m legal_mcp_assurance run \
  --transcript examples/broken-transcript.json \
  --format sarif --output assurance.sarif

PYTHONPATH=src python3 -m legal_mcp_assurance run \
  --transcript examples/good-transcript.json \
  --format junit --output assurance.xml
```

## Development

The test suite uses only `unittest`:

```sh
./ci/check.sh
```

That script runs the full suite and compiles all source and test modules. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Scope and limitations

Passing indicates that the sampled adapter responses met this profile's machine-checkable assertions. It is not a guarantee of completeness, correctness of the underlying legal materials, operational security, or fitness for a legal workflow. Transcript runs test recorded behavior; live behavior requires a separately maintained adapter and execution harness.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).

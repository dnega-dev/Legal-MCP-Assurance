# Contributing

Thank you for improving Legal MCP Assurance.

## Development requirements

- Python 3.9 or newer
- no third-party runtime packages
- tests written with the standard-library `unittest` package

## Local workflow

1. Create a focused branch in your own development environment.
2. Make changes under `src/`, `tests/`, `docs/`, or `examples/` as appropriate.
3. Add or update tests for both conforming and nonconforming behavior.
4. Run:

   ```sh
   ./ci/check.sh
   ```

5. Update `CHANGELOG.md` for user-visible changes.

## Design guidelines

- Preserve the transport-independent `ProviderAdapter` boundary. Core code must not open a network connection or launch a server.
- Keep runtime code within the Python standard library.
- Prefer deterministic, machine-readable results and explicit states over inference from missing fields.
- Assign a stable check ID and document all new canonical operations in `docs/profile-spec.md`.
- Never present a passing run as legal advice, legal validation, certification, or a guarantee about corpus completeness.
- Do not add real confidential source material to fixtures. Examples should be synthetic and clearly labeled.

## Tests

Name tests for observable behavior. Cover expected success, deliberate provider breakage, malformed transcripts, report validity, and CLI exit codes. Tests must not require network access or external services.

## Security reports

Do not open a public issue for a suspected vulnerability. Follow `SECURITY.md`.

## License

By contributing, you agree that your contributions are licensed under the Apache License 2.0.

# Security Policy

## Supported versions

The current `0.1.x` development line receives security fixes. This project is an MVP; users should review changes before deployment in sensitive environments.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the project maintainers through the repository's private security-reporting channel. Include:

- the affected version or commit;
- a minimal reproduction or malicious transcript, with sensitive data removed;
- expected and observed behavior;
- potential impact; and
- any suggested mitigation.

Do not include confidential legal materials, credentials, personal data, or production transcripts in a report. Maintainers should acknowledge a report within five business days and coordinate disclosure after a fix is available.

## Security model

Legal MCP Assurance parses local JSON and calls a supplied Python adapter. It does not implement MCP transport, authentication, subprocess isolation, or a network sandbox. Provider adapters execute with the permissions of the invoking process and must be reviewed separately.

Treat transcripts and report evidence as potentially sensitive. Use least-privilege filesystem access, avoid embedding secrets or privileged source text, and apply appropriate retention controls. Transcript fields are untrusted input; the built-in provider validates structure but does not make an untrusted adapter safe.

Assurance results describe sampled technical behavior and are not legal advice or a security certification.

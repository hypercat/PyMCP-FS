# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately. Do not open a public issue,
pull request, or discussion for a security problem.

Use GitHub's Private Vulnerability Reporting to open a private report:

https://github.com/hypercat/PyMCP-FS/security/advisories/new

This keeps the report confidential until a fix is available, gives us a private
thread to work in, and can be turned into a published advisory (with a CVE, if
one is warranted) once the issue is resolved.

## What to expect

- An acknowledgement within 7 days.
- An assessment of whether the report is accepted, with reasoning, within 14 days.
- For accepted reports, a fix or a documented mitigation, and coordination with
  you on timing before public disclosure.

This project is maintained in spare time, so please treat these as good-faith
targets rather than guarantees.

## Scope

PyMCP-FS grants an MCP client read and write access to a set of directories on
the host. Its central security property is that every file operation stays
inside the directories passed via `--directories`.

In scope:

- Any way to read, write, move, or enumerate a path outside the allowed
  directories.
- Any way to make `validate_path` accept a path it should reject, including
  traversal, symlink, junction, hardlink, or path-normalization tricks.
- Anything that causes the server to act outside the boundaries the operator
  configured.

Out of scope:

- Consequences of an operator deliberately allowing a sensitive directory. If
  you pass `--directories /`, the server will honor that.
- The behavior of the MCP client, or of the model driving it.
- Denial of service through very large files or deeply nested directory trees.

## Safe harbor

I will not pursue or support legal action against anyone who reports a
vulnerability in good faith through the channel above, who avoids privacy
violations and service disruption, and who allows reasonable time for a fix
before disclosing publicly.

# Security Policy

## Supported versions

Concord is currently pre-1.0. Security fixes target the default branch.

| Branch | Supported |
| --- | --- |
| `main` | Yes |
| Feature branches | No |
| Archived prototype branches | No |

## What to report

Please report issues that could affect Concord users, operators, or hosted deployments, including:

- API authentication or API key handling flaws.
- Tenant isolation bypasses.
- Exposure of traces, run reports, exported reports, secrets, or credentials.
- Server-side request forgery, command execution, path traversal, or injection issues.
- Unsafe handling of uploaded workflow YAML or JSON.
- Sandbox validation behavior that reports a pass when validation did not actually run.
- Cross-site scripting or auth bootstrap issues in the dashboard.
- CI, container, or deployment configuration that could leak credentials.

## Out of scope

The following are usually out of scope unless they demonstrate impact on Concord itself:

- Vulnerabilities in third-party services without a Concord integration flaw.
- Denial-of-service reports that only rely on high traffic volume.
- Social engineering or physical access attacks.
- Reports against local fixture data with no path to user data or credentials.
- Scanner output without a reproducible exploit or clear impact.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting flow if it is enabled for the repository:

1. Open the repository on GitHub.
2. Go to **Security**.
3. Choose **Report a vulnerability**.

If private reporting is not available, open a minimal public issue titled `Security contact request`. Do not include exploit details, secrets, tokens, private traces, or customer data in the public issue. A maintainer will provide a private path for details.

Include as much of the following as you can share safely:

- Affected commit, branch, or deployment.
- Clear reproduction steps.
- Expected impact.
- Logs, screenshots, or proof-of-concept details that do not expose third-party secrets.
- Whether the issue requires specific credentials or environment variables.

## Response expectations

Maintainers aim to:

- Acknowledge valid reports within 3 business days.
- Triage severity and reproducibility before discussing fixes publicly.
- Patch high-impact issues before publishing detailed advisories.
- Credit reporters when requested and appropriate.

This project does not currently run a paid bug bounty program.

## Safe testing

When testing Concord, please:

- Use your own local deployment or an explicitly authorized target.
- Do not access, modify, or delete data that is not yours.
- Do not exfiltrate secrets, traces, reports, or credentials.
- Stop testing and report promptly if you discover sensitive data.


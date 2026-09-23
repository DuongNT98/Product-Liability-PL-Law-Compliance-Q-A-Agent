# MFG-C2-066 — Product Liability & PL Law Compliance Q&A Agent

> **Category**: Cat 2 (multiple processing steps combined to complete one specific use case)
> **Industry**: Manufacturing

## Overview

Answers questions about Japan's Product Liability Act and related recall / consumer-safety
regulations, for manufacturers, product-safety teams, and legal or compliance staff.

Given a compliance or recall-procedure question — optionally with a defect type and
jurisdiction — the agent classifies the type of defect involved, retrieves the relevant
statutory and regulatory passages from its own knowledge base, and returns: the applicable
legal citation, the required action steps (e.g. a recall-notification procedure), and a
generic liability-exposure framing. Every answer carries a non-suppressible notice that this
is general compliance information, not a substitute for individualized legal advice, and asks
the reader to consult a licensed attorney for any specific incident.

It deliberately does not decide: it never quantifies liability or fault for a specific
incident, and it does not replace legal counsel for an actual recall or litigation decision.
Answers are limited to general regulatory guidance grounded in the template's own knowledge
base of law text and guidelines — an out-of-date or incomplete knowledge base is a real
operating limit, not a hidden one.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | >=3.11 |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and operational documentation
```

See `docs/` for the design spec and test specification.

## Customising

1. Adjust `config/` for your own environment and policies.
2. Replace the knowledge sources and sample data with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.

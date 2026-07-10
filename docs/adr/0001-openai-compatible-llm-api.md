# 0001: Use the OpenAI-compatible API for LLM access

- Status: accepted
- Date: 2026-07-10

## Context

Resolves D2 in SPECIFICATION.md §9. The AI referee needs an LLM backend. The
project owner runs models locally via Ollama and vLLM, both of which expose
the OpenAI chat-completions API, and wants freedom to swap models without code
changes.

## Decision

All LLM access goes through the OpenAI-compatible chat-completions API,
configured by base URL and model name (plus an optional API key). No
provider-specific SDK in the core; Ollama, vLLM, and hosted OpenAI-compatible
endpoints are interchangeable backends.

## Consequences

- Local-first play with no vendor lock-in; backends swap via configuration.
- Tool and function-calling quality varies widely across local models. The GM
  agent (FR-12) must probe backend capability and fall back to constrained or
  structured output (e.g. JSON schema prompting) when native tool-calling is
  unreliable (NFR-6).
- Local context windows can be small (4k–32k), which pushes SRD and module
  grounding (D3) toward retrieval and distilled procedure documents rather
  than full-document context.
- Provider-specific features (prompt caching, server-side tools) are off the
  table unless exposed through the compatible API surface.

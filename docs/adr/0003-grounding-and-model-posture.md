# 0003: Hybrid SRD grounding; hosted frontier models as primary target

- Status: accepted
- Date: 2026-07-10

## Context

Resolves D3 in SPECIFICATION.md §9. The GM agent must apply SRD procedure
correctly every turn (position/effect, consequences, the score loop) and also
answer arbitrary rules questions. ADR-0001 fixed the API shape
(OpenAI-compatible) but left open which class of model is the design target,
which in turn determines how much rules text can live in the prompt.

## Decision

**Primary backend: hosted, frontier-class models behind an OpenAI-compatible
endpoint, with a working context of 64k–128k tokens.** Local backends
(Ollama, vLLM) remain fully supported via the same client abstraction,
best-effort: the capability probe and structured-output fallback (NFR-6) are
still built, but small-context local models are not the constraint the system
is designed around.

**Grounding: hybrid.**

1. Distilled procedure documents (hand-written, compact summaries of the
   GM-critical procedures: action roll flow, setting position and effect,
   consequence menu, score/downtime loop, GM goals and principles) are always
   present in the system prompt. The GM never has to retrieve its own job
   description.
2. Retrieval over the full SRD (and later, ingested modules per FR-24) covers
   rules lookups, edge cases, and citations (FR-13). Answers to rules
   questions quote retrieved passages, not model memory.

## Consequences

- Authoring the distilled procedure docs is a real Phase 4 work item, and they
  must cite the SRD sections they compress so drift is checkable (NFR-2).
- Retrieval needs an index over chunked SRD text. Lexical BM25 is an
  acceptable first version and avoids an embedding-model dependency; the
  implementation is chosen in Phase 4.
- Native tool-calling is dependable in the common case; the fallback path
  is covered by the test suite (with a fake backend) so it does not rot.
- 64k–128k is comfortable but not unlimited: the full SRD (about 50k tokens)
  never goes in whole. Each GM turn is assembled under an explicit context
  budget, roughly: system prompt and distilled procedures 8k or less, active
  canon slice 10k or less, retrieved rules passages 4k or less, recent
  transcript 25k or less with older play summarised. That leaves headroom at
  64k. The context assembler enforces the budget (NFR-4).

# 0007: Canvas library for Table view v2 (district/score maps)

- Status: accepted
- Date: 2026-07-11

## Context

D4 (ADR-0002) deferred picking a canvas library for maps until the map view
was actually being built. TODO.md's Phase 5 "Table view v2: generated
district/score maps (FR-29)" is that point. FR-29 wants the crew's claim map
and district/score maps as shared fiction aids; §3's non-goals rule out a
tactical VTT (no token combat, no measured grid) and any AI-generated
artwork pipeline (C3) - so this is a light diagrammatic map (shapes, labels,
connections between locations/districts), not a game surface, and never
photographic/painted art.

Two contenders, as named in D4:

- **Pixi.js** (`@pixi/react` bindings): a WebGL-first 2D renderer built for
  games - sprites, filters, particle effects, a render loop. Its React
  bindings exist but the ecosystem is sparser (npm trends: pixi.js sits at
  roughly half react-konva's weekly downloads, and the dedicated React
  binding packages trail further behind).
- **Konva.js** (`react-konva` bindings): a Canvas2D scene-graph framework
  built for exactly this shape - interactive diagrams with click/drag/hover,
  a node/group tree, and shape primitives (rects, labels, arrows for
  connections) that map directly onto "districts as nodes, claims as
  markers, adjacency as lines". `react-konva` is maintained by the same team
  as Konva itself, versioned alongside React majors (currently React
  19-compatible), and is the more widely-adopted React canvas binding.

Neither app needs WebGL-scale throughput: at most a few dozen districts/
locations and claims render at once, well within what Canvas2D handles
without dropping frames. Pixi's strengths (sprite batching, shaders,
particle systems, a persistent render loop) go mostly unused for a static-
until-clicked diagram; Konva's strengths (scene graph, built-in hit
detection on arbitrary shapes, drag/drop, an event system that mirrors DOM
events) are exactly what a clickable claim/district map needs.

## Decision

**Konva.js via `react-konva`** for Table view v2's district/score maps and
the claim map's eventual visual upgrade (today's Table view v1 claim list
stays a plain list until this lands).

- Map data (locations/districts, their connections, and where a claim or
  score sits among them) needs a structured shape that doesn't exist yet:
  `CampaignCanon.locations` (`engine/campaign.py`) is a flat `list[str]`,
  and `ClaimSnapshot` carries no position/adjacency at all. Designing that
  data model - and how session-zero's generation flow (FR-36) populates it -
  is separate follow-up work this ADR doesn't resolve, only unblocks by
  fixing the rendering technology.
- Rendering stays purely client-side: the server never generates map
  imagery (C3, "No AI-generated artwork pipeline") - only the structured
  location/connection/claim data `react-konva` draws from.

## Consequences

- One new web dependency (`konva` + `react-konva`); no new server
  dependency, no new API shape beyond whatever the location/connection data
  model ends up needing.
- Konva's shape primitives (`Rect`, `Circle`, `Line`, `Arrow`, `Text`,
  `Group`) cover districts-as-nodes/claims-as-markers/adjacency-as-lines
  directly; no custom hit-testing or drag logic needs hand-rolling.
- If a future need genuinely requires WebGL-scale rendering (hundreds of
  animated tokens, particle effects) this decision would need revisiting -
  not expected given §3's non-goals, but worth naming as the condition that
  would reopen it.

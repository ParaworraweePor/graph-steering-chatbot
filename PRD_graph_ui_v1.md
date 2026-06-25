# PRD: Graph UI — Layout Fix + Node Colour System
**Version:** UI-1.0
**Scope:** `cbt_kg/ui.py` only (no ontology or pipeline changes)
**Depends on:** PRD v7.1 graph data shape (nodes carry `.label`, `.status`, `.props`)

---

## 1. Problem

Two independent issues make the graph panel hard to read:

1. **Layout clumping.** When a session produces many nodes (5+ Reactions, 3+
   CoreBeliefs, multiple Situations), they pile on top of each other. The root
   causes are (a) horizontal spacing capped at 120 px regardless of canvas width,
   (b) spring-force repulsion too weak at 2 200/(dist²) to push nodes apart within
   the same layer, (c) the `layoutDone = true` flag that prevents re-layout when
   new nodes arrive during a session, and (d) RIGHT_SIDE nodes stacked at a fixed
   80 px gap that runs off-canvas with 3+ Interventions/Homework items.

2. **Every node looks alike.** The current palette assigns the same purple fill to
   all cognitive-model classes (CoreBelief, IntermediateBelief, Situation,
   AutomaticThought, Reaction, AdaptiveResponse) and the same amber to both
   Intervention and Homework. With a dense graph, it's impossible to distinguish
   classes without reading every label.

---

## 2. Solution

### 2.1 Per-class colour system (from `neo4j_style.grass`)

Replace the three Python dicts (`COLOR`, `BADGE_BG`, `BADGE_COLOR`) and their
JavaScript counterparts with the exact values from `neo4j_style.grass`, mapped to
the three canvas roles: **fill** (`color`), **stroke** (`border-color`), and
**text** (`text-color-internal`).

Classes not present in the current V4_flat ontology (OpeningSegment, WorkingSegment,
ClosingSegment, AgendaItem, MoodRating, Diagnosis) are **ignored**.
`AdaptiveResponse` and `Client` are not in the grass file — derive them as specified
below.

#### Complete colour table

| Class | Fill | Stroke | Text |
|---|---|---|---|
| `Client` | `#E5E7EB` | `#D1D5DB` | `#1F2937` |
| `Session` | `#E5E7EB` | `#D1D5DB` | `#1F2937` |
| `Problem` | `#F87171` | `#EF4444` | `#FFFFFF` |
| `Goal` | `#34D399` | `#10B981` | `#1F2937` |
| `Intervention` | `#A78BFA` | `#8B5CF6` | `#FFFFFF` |
| `Homework` | `#FBBF24` | `#F59E0B` | `#1F2937` |
| `CoreBelief` | `#9D174D` | `#831843` | `#FFFFFF` |
| `IntermediateBelief` | `#BE185D` | `#9D174D` | `#FFFFFF` |
| `Situation` | `#FDE047` | `#FACC15` | `#1F2937` |
| `AutomaticThought` | `#6EE7B7` | `#34D399` | `#1F2937` |
| `Reaction` | `#FCA5A5` | `#F87171` | `#1F2937` |
| `AdaptiveResponse` | `#D1FAE5` | `#6EE7B7` | `#065F46` |
| `Utterance` | `#D1D5DB` | `#9CA3AF` | `#1F2937` |
| `missing` (any class) | `#F5F5F5` | `#AAAAAA` (dashed) | `#AAAAAA` |

> **AdaptiveResponse** is not in the grass file. Derive it one tone lighter
> than AutomaticThought (same green family): fill `#D1FAE5`, stroke `#6EE7B7`,
> text `#065F46`. This keeps it visually grouped with AT while remaining distinct.
>
> **Client** is not in the grass file. Use the same values as Session — they are
> both structural anchors at the top of the graph and the visual grouping is correct.

#### Where these values live in the code

Two locations must be updated together and kept in sync:

**`ui.py` (Python) — the dicts injected into the HTML template:**

```python
# Replace the existing COLOR / BADGE_BG / BADGE_COLOR dicts with:

NODE_COLORS: dict[str, tuple[str, str, str]] = {
    # label: (fill, stroke, text)
    "Client":              ("#E5E7EB", "#D1D5DB", "#1F2937"),
    "Session":             ("#E5E7EB", "#D1D5DB", "#1F2937"),
    "Problem":             ("#F87171", "#EF4444", "#FFFFFF"),
    "Goal":                ("#34D399", "#10B981", "#1F2937"),
    "Intervention":        ("#A78BFA", "#8B5CF6", "#FFFFFF"),
    "Homework":            ("#FBBF24", "#F59E0B", "#1F2937"),
    "CoreBelief":          ("#9D174D", "#831843", "#FFFFFF"),
    "IntermediateBelief":  ("#BE185D", "#9D174D", "#FFFFFF"),
    "Situation":           ("#FDE047", "#FACC15", "#1F2937"),
    "AutomaticThought":    ("#6EE7B7", "#34D399", "#1F2937"),
    "Reaction":            ("#FCA5A5", "#F87171", "#1F2937"),
    "AdaptiveResponse":    ("#D1FAE5", "#6EE7B7", "#065F46"),
    "Utterance":           ("#D1D5DB", "#9CA3AF", "#1F2937"),
}
MISSING_COLORS = ("#F5F5F5", "#AAAAAA", "#AAAAAA")
```

Then build the three existing JS dicts from `NODE_COLORS` at template-render time:

```python
COLOR     = {k: v[1] for k, v in NODE_COLORS.items()}   # stroke → outline colour
BADGE_BG  = {k: v[0] for k, v in NODE_COLORS.items()}   # fill
BADGE_CLR = {k: v[2] for k, v in NODE_COLORS.items()}   # text
COLOR["missing"] = MISSING_COLORS[1]
```

**`graph_memory.py` — `_TYPE_BY_LABEL` and `_cytoscape_render`:**

`_TYPE_BY_LABEL` currently groups classes into 4 buckets (`session`,
`session_structure`, `cognitive`, `provenance`) which is what drives colours in the
old palette. This grouping is **no longer needed for colour** once the canvas uses
per-class colour. Keep the dict for any non-colour logic (e.g. legend grouping) but
do not derive colours from it in the canvas renderer.

#### Legend update

The legend in the canvas HTML must be rebuilt to show all 13 classes, not 4
groups. Use two rows:

```
Row 1 (session/structure):  Client · Session · Problem · Goal · Intervention · Homework
Row 2 (cognitive model):    CoreBelief · IntermBelief · Situation · AutoThought · Reaction · AdaptResponse
Row 3 (other):              Utterance · ── found edge · ╌╌ placeholder
```

Each legend dot uses the class's fill colour with the stroke as its CSS border.
Text uses the class's text colour rendered on the fill background.

#### Inspector badge

The Inspector panel's class badge (shown when a node is selected) already uses
`BADGE_BG[n.label]` and `BADGE_COLOR[n.label]`. Once the dicts above are updated
it will automatically render with the correct per-class colour. No additional change
needed.

---

### 2.2 Layout algorithm replacement

Replace the `applyLayout` function in the canvas `<script>` block with the
following specification. The function signature is unchanged:
`function applyLayout(W, H)`.

#### Layer definitions (unchanged)

```js
const LAYERS = {
  Client: 0, Session: 1,
  Problem: 2, Goal: 2,
  CoreBelief: 3, IntermediateBelief: 3,
  Situation: 4, AutomaticThought: 4,
  Reaction: 5, AdaptiveResponse: 5,
};
const RIGHT_SIDE = new Set(["Intervention", "Homework"]);
```

#### Step 1 — Initial positions (hierarchical slot assignment)

```
MARGIN = 48 px
RIGHT_W = 160 px        (column width reserved for RIGHT_SIDE nodes)
MAIN_W = W - RIGHT_W - MARGIN * 2

For each layer L (sorted ascending):
  row = nodes where LAYERS[label] === L
  count = row.length
  slotW = MAIN_W / count                     ← full-width slot, not capped at 120px
  for i in 0..count-1:
    row[i].x = MARGIN + slotW * i + slotW / 2
    row[i].y = MARGIN + layerIndex(L) * layerH
      where layerH = (H - MARGIN*2) / (totalLayers - 1)

For RIGHT_SIDE nodes, group by label (Intervention group, then Homework group):
  rightLabelH = (H - MARGIN*2) / rightLabelCount
  within each group: distribute evenly in their vertical slot
```

#### Step 2 — Spring-force refinement (80 iterations, annealed)

```
Repulsion (all pairs):
  rep = min(8000 / dist², 60)       ← stronger than old 2200; capped to prevent explosion
  apply: force_x += ux * rep
         force_y += uy * rep * 0.15  ← strongly damp vertical to preserve layer structure

Attraction (connected pairs):
  ideal_dist = 130 px
  att = (dist - ideal_dist) * 0.03
  apply along edge direction (x and y equally)

Damping: step = 0.4 × 0.97^iter    ← annealed, starts 0.4, decays to ~0.04 at iter 80

Boundary constraints per iteration:
  Main nodes: clamp x to [MARGIN+20, MARGIN+MAIN_W-20]
              clamp y to [yBase-25, yBase+25]   (stay within ±25 px of their layer y)
  RIGHT_SIDE:  clamp x to [W-RIGHT_W-10, W-30]
               clamp y to [30, H-30]
```

#### Step 3 — When to re-run layout

**Remove the `layoutDone` flag entirely.** Replace it with:

```js
let lastNodeCount = 0;

// Inside the polling fetchAndRender (Part 1 live graph):
if (data.nodes.length !== lastNodeCount) {
    applyLayout(W, H);
    lastNodeCount = data.nodes.length;
}
```

For Part 2 (graph loaded from JSON or Neo4j): run `applyLayout` once immediately
after the graph data is assigned, before `draw()`.

#### Step 4 — Edge rendering: bezier curves

Replace straight-line edges with light bezier curves to prevent parallel edges
between the same pair of nodes from overlapping. The control point offset is
proportional to the edge's index among same-pair edges:

```js
// For each edge, compute control-point offset:
const ux = dx/dist, uy = dy/dist;
const CURVE = 28;                         // base lateral offset in px
const lateralOffset = uy * CURVE;         // perpendicular to edge direction (swap x↔y, negate one)
const cx1 = sx + uy*CURVE, cy1 = sy - ux*CURVE;
const cx2 = ex + uy*CURVE, cy2 = ey - ux*CURVE;
ctx.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);

// Arrow head: use the final bezier tangent, not atan2(ey-sy, ex-sx):
const ang = Math.atan2(ey - cy2, ex - cx2);
```

The edge label is placed at the bezier midpoint (approx. at `t=0.5`) offset
slightly outward: `mx = (sx+ex)/2 + uy*CURVE*0.5; my = (sy+ey)/2 - ux*CURVE*0.5`.

#### Step 5 — Node radius constants

Use **separate radius constants** for hit-testing and drawing to avoid arrowhead
overlap:

```js
const RADIUS_CIRCLE = 28;    // draw radius for circle nodes
const RADIUS_RECT_H = 22;    // half-height for rect nodes (Problem, Goal)
const RADIUS_RECT_W = 38;    // half-width for rect nodes
const ARROW_CLEARANCE = 8;   // extra px gap between arrowhead and node edge
```

Edge start/end offsets:
```js
const startR = RECT_LABELS.has(a.label) ? RADIUS_RECT_H : RADIUS_CIRCLE;
const endR   = RECT_LABELS.has(b.label) ? RADIUS_RECT_H : RADIUS_CIRCLE;
const sx = a.x + ux*(startR), sy = a.y + uy*(startR);
const ex = b.x - ux*(endR + ARROW_CLEARANCE), ey = b.y - uy*(endR + ARROW_CLEARANCE);
```

---

## 3. Files changed

| File | Change |
|---|---|
| `ui.py` | Replace `COLOR`, `BADGE_BG`, `BADGE_COLOR` dicts with `NODE_COLORS` table (§2.1). Update the three JS constants injected into the template. Rebuild the legend HTML (§2.1 legend). Replace `applyLayout` JS function (§2.2). Remove `layoutDone` flag; add `lastNodeCount` re-layout trigger (§2.2 step 3). Replace straight-line edge draw with bezier (§2.2 step 4). Apply node radius constants (§2.2 step 5). |
| `graph_memory.py` | Keep `_TYPE_BY_LABEL` but stop deriving colours from it in the renderer. No other change. |

No changes to `ontology.py`, `extract.py`, `therapy.py`, `query.py`, `api.py`, or
any test files.

---

## 4. Acceptance criteria

- Every V4_flat class renders with its own distinct fill, stroke, and text colour
  exactly matching the table in §2.1.
- Colours match `neo4j_style.grass` values exactly (no approximation) for the 11
  classes present in the file.
- `AdaptiveResponse` and `Client` render with the derived colours specified in §2.1.
- Missing nodes (any class) render with fill `#F5F5F5`, dashed stroke `#AAAAAA`,
  text `#AAAAAA` regardless of class.
- Selected node highlights with a coral (`#D85A30`) outline glow; class colour
  remains as the fill.
- With 20 nodes matching the screenshot data, no two nodes overlap after
  `applyLayout` runs.
- Adding nodes during a live session (Part 1 polling) triggers a new layout run
  only when `nodes.length` changes; existing dragged positions are not preserved
  across re-layouts (acceptable for demo).
- Parallel edges between the same node pair curve away from each other and are
  individually readable.
- The legend shows all 13 classes in two rows, each dot coloured correctly.
- Inspector badge renders each class in its correct fill/text colour.

---

## 5. Not in scope

- Zoom / pan on the canvas (deferred).
- Preserving user-dragged positions across polling updates (deferred).
- Animated edge drawing (deferred).
- Dark-mode colour variants — the grass palette is light-mode only; accepted for
  the demo.

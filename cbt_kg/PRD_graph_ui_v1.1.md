# PRD: Graph UI — Readability, Overlap, Placeholder & Viewport Fixes
**Version:** UI-1.1
**Scope:** `cbt_kg/ui.py` and `cbt_kg/graph_memory.py`
**Depends on:** PRD UI-1.0 (colour system + layout). This patches issues found
after UI-1.0 landed.

---

## 1. Problems (from live screenshots)

1. **Property text is unreadable.** The second line of each node (the property
   preview, e.g. "social", "breakups in m…") is drawn in the node's **stroke
   colour**. On dark-fill classes (CoreBelief `#9D174D`, IntermediateBelief
   `#BE185D`, Intervention `#A78BFA`) dark text on a dark fill is invisible.

2. **Nodes overlap badly at scale.** At 49 nodes / 59 edges the layout collapses —
   many same-class nodes (6 Reactions, 7 Interventions, 6 Homework, multiple
   CoreBeliefs) pile on top of each other and labels are unreadable.

3. **Placeholder relations create a disconnected mess.** Missing (placeholder)
   edges are rendered as dashed grey lines between placeholder nodes. In a
   sparse early graph this produces a spider-web of grey dashes that don't
   reflect anything real and obscure the few found edges. **Decision: stop
   emitting placeholder edges entirely — only show edges once found.**

4. **No zoom or pan.** The canvas supports node dragging only. With a large graph
   the user cannot zoom out to see the whole structure or pan around it.

---

## 2. Fixes

### 2.1 Fix property text colour (`ui.py`, `draw()` node loop)

The node draws two text lines: the class label and the property preview. Both
must use the node's **text colour** from the colour table, never the stroke
colour.

**Current (broken):**
```js
// class label — correct
ctx.fillStyle = isMissing ? '#aaa' : (BADGE_COLOR[n.label] || '#333');
ctx.fillText(shortLabel, n.x, n.y - 7);
// property preview — WRONG: uses stroke colour `col`
ctx.fillStyle = isMissing ? '#ccc' : col;
ctx.fillText(shortProp, n.x, n.y + 6);
```

**Fixed:**
```js
const nodeTextCol = isMissing ? '#9aa0a6' : (BADGE_COLOR[n.label] || '#1F2937');
// class label
ctx.fillStyle = nodeTextCol;
ctx.font = '600 9px system-ui,sans-serif';
ctx.fillText(shortLabel, n.x, n.y - 7);
// property preview — same text colour, slightly lighter via globalAlpha
ctx.save();
ctx.globalAlpha = isMissing ? 1 : 0.82;
ctx.fillStyle = nodeTextCol;
ctx.font = '8px system-ui,sans-serif';
ctx.fillText(shortProp, n.x, n.y + 6);
ctx.restore();
```

Using the same text colour at 82 % alpha gives a readable second line on every
fill (white text on dark fills, dark text on light fills) while keeping it
visually subordinate to the class label.

> The `BADGE_COLOR` values from UI-1.0 already encode correct contrast per class
> (white `#FFFFFF` on CoreBelief/IntermediateBelief/Problem/Intervention, dark
> `#1F2937` on light fills). This fix simply routes the property text through the
> same value.

### 2.2 Stop emitting placeholder edges (`graph_memory.py`, `_cytoscape_render`)

Placeholder edges are the source of the disconnected dashed web. Remove them from
the render output. Keep placeholder **nodes** (they're useful to show which
classes haven't appeared yet), but only render an edge once it is `found`.

**Current:**
```python
out_edges = []
for e in edges:
    out_edges.append({"data": {
        "id": e.edge_id,
        "source": e.subject_id,
        "target": e.object_id,
        "label": e.predicate if e.status == "found" else "",
        "predicate": e.predicate,
        "status": e.status,
    }})
```

**Fixed:**
```python
out_edges = []
for e in edges:
    if e.status != "found":
        continue                      # skip placeholder edges entirely
    out_edges.append({"data": {
        "id": e.edge_id,
        "source": e.subject_id,
        "target": e.object_id,
        "label": e.predicate,
        "predicate": e.predicate,
        "status": e.status,
    }})
```

This applies to both Part 1 (live) and Part 2 (loaded graphs) since both go
through `_cytoscape_render` / `cytoscape_render`.

**Consequences to handle in `ui.py`:**
- The JS edge-draw branch for `status !== 'found'` (dashed grey) becomes dead code
  for incoming data. Keep the dashed style only for the **edit-mode** "placeholder"
  edges a user may create in Part 2; otherwise all rendered edges are solid found
  edges.
- Update the legend: remove the "╌╌ Placeholder" entry from the **Part 1** legend
  (there are no placeholder edges to show). Keep it in **Part 2** edit mode only,
  where a user can manually set an edge's status.

> **Note on placeholder *nodes*:** these are kept. A class that hasn't appeared yet
> still shows as a grey dashed circle so the user sees the full ontology surface.
> Only the *edges* between them are suppressed. This removes the web while keeping
> the "what's still missing" affordance.

### 2.3 Fix overlap at scale (`ui.py`, `applyLayout`)

UI-1.0's layout handles ~20 nodes. At 49 nodes the per-layer rows overflow. Three
adjustments:

**(a) Wrap dense layers into sub-rows.** When a layer has more than `MAX_PER_ROW`
(= 6) nodes, split it into multiple stacked sub-rows within that layer's vertical
band instead of cramming them into one horizontal line.

```js
const MAX_PER_ROW = 6;
const SUBROW_GAP = 64;                 // vertical px between sub-rows in a layer

for (const L of sortedLayers) {
  const row = nodesInLayer(L);
  const subRows = Math.ceil(row.length / MAX_PER_ROW);
  const yBase = MARGIN + layerIndex(L) * layerH;
  for (let i = 0; i < row.length; i++) {
    const sr = Math.floor(i / MAX_PER_ROW);
    const idxInSr = i % MAX_PER_ROW;
    const cntInSr = Math.min(MAX_PER_ROW, row.length - sr * MAX_PER_ROW);
    const slotW = MAIN_W / cntInSr;
    row[i].x = MARGIN + slotW * idxInSr + slotW / 2;
    row[i].y = yBase + (sr - (subRows - 1) / 2) * SUBROW_GAP;
  }
}
```

**(b) Increase the per-node minimum separation.** Bump repulsion and the boundary
clamp so dense sub-rows still breathe.

```js
const rep = Math.min(12000 / (dist * dist), 90);   // was 8000 / cap 60
const MIN_SEP = 68;                                 // hard minimum centre-to-centre
// after force step, run a short relaxation pass:
for (let i=0;i<nodes.length;i++) for (let j=i+1;j<nodes.length;j++){
  const a=nodes[i],b=nodes[j];
  let dx=b.x-a.x, dy=b.y-a.y, d=Math.hypot(dx,dy)||1;
  if (d < MIN_SEP){
    const push=(MIN_SEP-d)/2, ux=dx/d, uy=dy/d;
    a.x-=ux*push; a.y-=uy*push*0.5; b.x+=ux*push; b.y+=uy*push*0.5;
  }
}
```

**(c) Grow the virtual canvas for big graphs.** Instead of clamping all nodes into
the visible viewport, let the layout use a larger virtual space and rely on
zoom-to-fit (§2.4) to bring it into view.

```js
const NODE_COUNT = nodes.length;
const SCALE = Math.max(1, Math.sqrt(NODE_COUNT / 18));   // grow with node count
const VW = W * SCALE, VH = H * SCALE;                    // virtual layout dimensions
// run applyLayout against VW/VH instead of W/H; then zoomToFit() maps it to the viewport
```

### 2.4 Add zoom + pan (`ui.py`, canvas viewport transform)

Introduce a viewport transform applied before drawing. This is the largest change
but is self-contained in the canvas script.

**State:**
```js
let view = { scale: 1, tx: 0, ty: 0 };   // world→screen: screen = world*scale + t
```

**Apply in `draw()`** (wrap all node/edge drawing):
```js
function draw() {
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  ctx.translate(view.tx, view.ty);
  ctx.scale(view.scale, view.scale);
  // ... existing edge + node drawing in WORLD coordinates ...
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);   // reset for next frame
}
```

**Screen→world helper** (needed for hit-testing and dragging):
```js
function toWorld(sx, sy) {
  return { x: (sx - view.tx) / view.scale, y: (sy - view.ty) / view.scale };
}
```
Update `nodeAt`/`edgeAt`/drag handlers to convert the mouse position with
`toWorld()` before comparing to node coordinates.

**Wheel to zoom (centred on cursor):**
```js
cv.addEventListener('wheel', e => {
  e.preventDefault();
  const r = cv.getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  const before = toWorld(mx, my);
  const factor = e.deltaY < 0 ? 1.1 : 1/1.1;
  view.scale = Math.max(0.2, Math.min(3, view.scale * factor));
  // keep cursor point stationary:
  view.tx = mx - before.x * view.scale;
  view.ty = my - before.y * view.scale;
  draw();
}, { passive: false });
```

**Drag to pan (empty space) vs drag node (on a node):**
```js
let panning = null;
cv.addEventListener('mousedown', e => {
  const r = cv.getBoundingClientRect();
  const w = toWorld(e.clientX - r.left, e.clientY - r.top);
  const n = nodeAt(w.x, w.y);
  if (n) { drag = n; dragOff = { x: w.x - n.x, y: w.y - n.y }; selectItem('node', n.id); return; }
  const ed = edgeAt(w.x, w.y);
  if (ed) { selectItem('edge', ed.id); return; }
  panning = { sx: e.clientX, sy: e.clientY, tx0: view.tx, ty0: view.ty };
  clearSelection();
});
cv.addEventListener('mousemove', e => {
  const r = cv.getBoundingClientRect();
  if (drag) {
    const w = toWorld(e.clientX - r.left, e.clientY - r.top);
    drag.x = w.x - dragOff.x; drag.y = w.y - dragOff.y; draw(); return;
  }
  if (panning) {
    view.tx = panning.tx0 + (e.clientX - panning.sx);
    view.ty = panning.ty0 + (e.clientY - panning.sy);
    draw();
  }
});
cv.addEventListener('mouseup', () => { drag = null; panning = null; });
```

**Zoom-to-fit** (run after layout and on a "Fit" button):
```js
function zoomToFit(pad = 40) {
  if (!nodes.length) return;
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
  for (const n of nodes){ minX=Math.min(minX,n.x);minY=Math.min(minY,n.y);
                          maxX=Math.max(maxX,n.x);maxY=Math.max(maxY,n.y); }
  const gw = (maxX-minX)||1, gh = (maxY-minY)||1;
  view.scale = Math.max(0.2, Math.min(3, Math.min((W-pad*2)/gw, (H-pad*2)/gh)));
  view.tx = (W - gw*view.scale)/2 - minX*view.scale;
  view.ty = (H - gh*view.scale)/2 - minY*view.scale;
  draw();
}
```

**Toolbar buttons** (add to the existing `graph-actions` header, both Part 1 and
Part 2): `Fit` (calls `zoomToFit()`), `＋` / `－` (zoom by 1.2 centred on canvas
middle), `Reset` (re-run `applyLayout` then `zoomToFit`). The existing edit-mode
buttons (`+ Node`, `+ Edge`, `Save JSON`) remain in Part 2.

**Call `zoomToFit()`** automatically:
- After the initial `applyLayout` on first data.
- In Part 1 polling, only when `nodes.length` changes (alongside the
  re-layout trigger from UI-1.0) — do **not** re-fit on every poll, or the view
  will jump while the user is inspecting.

---

## 3. Files changed

| File | Change |
|---|---|
| `ui.py` | (§2.1) property text uses `BADGE_COLOR` at 0.82 alpha. (§2.3) `applyLayout`: sub-row wrapping, stronger repulsion + `MIN_SEP` relaxation, virtual-canvas scaling. (§2.4) viewport transform: `view` state, `toWorld`, wheel-zoom, pan, `zoomToFit`, toolbar buttons; hit-testing via `toWorld`. Legend: drop placeholder-edge entry in Part 1. |
| `graph_memory.py` | (§2.2) `_cytoscape_render` skips edges where `status != "found"`. |

No changes to `ontology.py`, `extract.py`, `therapy.py`, `query.py`, `api.py`,
tests, or the colour table from UI-1.0.

---

## 4. Acceptance criteria

- Property preview text is legible on **every** class fill, including the dark
  ones (CoreBelief, IntermediateBelief, Intervention, Problem).
- No dashed grey placeholder edges appear in Part 1 or in a loaded Part 2 graph;
  only found edges render. Placeholder **nodes** still appear as grey dashed
  circles.
- At 49 nodes / 59 edges, no two nodes overlap; dense layers wrap into stacked
  sub-rows; all class labels are readable after `zoomToFit`.
- Mouse wheel zooms centred on the cursor; scale clamped to [0.2, 3].
- Dragging empty space pans; dragging a node moves only that node; clicking a
  node/edge still opens the Inspector.
- `Fit` button frames the whole graph; `Reset` re-lays-out and re-fits.
- In Part 1, the view auto-fits only when the node count changes, not on every
  3 s poll (no view jump while inspecting).
- Hit-testing remains accurate at any zoom/pan offset.

---

## 5. Not in scope

- Touch/pinch gestures (mouse wheel + drag only for the demo).
- Edge bundling for very dense hubs (the Session/Intervention hub may still be
  busy; acceptable).
- Persisting view state across reloads.
- Animated transitions on zoom/pan.

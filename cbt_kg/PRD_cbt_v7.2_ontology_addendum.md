# PRD Addendum: Ontology Changes (Ground-Truth Confirmed) — v7.2
**Version:** 7.2 (addendum to v7.1 §3, the ontology reference)
**Trigger:** `demo1_ground_truth_v4_flat.json` — a hand-built gold-standard
extraction over a 45-turn transcript, produced against `cbt_kg_ontology_v4_flat.txt`.
**Status:** This is the authoritative tie-breaker wherever v7.1 was ambiguous.
Where this addendum conflicts with v7.1 §3, **this addendum wins** — update
`ontology.py` and `test_ontology.py` accordingly.

---

## 1. Hard ontology change — remove `CoreBelief influencesPerceptionOf Situation`

The gold file's `exclusions` list states this explicitly:

> *"CoreBelief influencesPerceptionOf Situation — Dropped in V4 — mediated through
> IntermediateBelief only."*

**This edge signature must be deleted from `ANCHOR_FAMILIES` and
`ALLOWED_SIGNATURES`.** The only `influencesPerceptionOf` signature is:

```
IntermediateBelief --influencesPerceptionOf--> Situation
```

**Action for `ontology.py`:**
- Remove `CoreBelief` from any `influencesPerceptionOf` entry if present.
- Add this pair explicitly to `DISJOINT_RULES` (§3.4.7 of v7.1) so the Tier-A
  edge step and the Part-2 manual editor both reject it:
  ```python
  DISJOINT_RULES = [
    ("AutomaticThought", "*", "AutomaticThought"),
    ("CoreBelief", "influencesPerceptionOf", "Situation"),   # ← confirm present
    ("Intervention", "appliedTo", "Goal"),
  ]
  ```
  (v7.1 already listed this in §3.4.7 as a disjoint rule — the gold file
  confirms it is correct and must not be relaxed. No silent regression here;
  this addendum is making sure it's actually enforced in code, since the
  hierarchy diagram in §3.0 could be misread as allowing a `CoreBelief`→`Situation`
  shortcut.)

**Cognitive chain, corrected direction of travel:**
```
CoreBelief --givesRiseTo--> IntermediateBelief --influencesPerceptionOf--> Situation --triggers--> AutomaticThought
```
A `CoreBelief` only reaches a `Situation` by passing through an
`IntermediateBelief`. There is no skip-level edge.

---

## 2. Extraction-judgment rules clarified by the gold file (no schema change, but must be encoded in prompts/few-shots)

These don't change `ontology.py`'s structure, but they are **judgment calls** the
Tier-A/Tier-B extraction prompts must be trained to make correctly. Add them as
few-shot guidance in `prompts.py`.

### 2.1 Multiple CoreBeliefs in one session are expected and must be kept distinct

The gold file has **two** CoreBeliefs (`worthless` / domain=self, and
`unlovable` / domain=self) from the same client in the same session, each with
its own `stemsFrom` branch of AutomaticThoughts:

```
AT1, AT2, AT3  (love / alone / wanted branch)  --stemsFrom--> CB2 (unlovable)
AT4, AT5       (wrong / haven't done good job)  --stemsFrom--> CB1 (worthless)
AT7            (fear of judgment)               --stemsFrom--> CB1 (worthless)
```

**Action for `prompts.py` (MERGE step, §4.1 step 4 of v7.1):** the merge/dedup
step must not collapse two distinct CoreBeliefs into one just because they
share `domain=self`. Category (`helpless`/`unlovable`/`worthless`) is a strong
dedup signal — **do not merge CoreBeliefs across different `category` values**,
even if their Jaccard text similarity is moderate. Two beliefs with different
categories are different nodes by definition.

> The gold file's note makes this explicit: *"Category is NOT just a keyword
> match — it reflects what the client expressed through understanding."* This
> means the property-classification step (Stage 2.5, v7.1 §4.1 step 3) must
> read the surrounding turns for meaning, not pattern-match on words like
> "worthless" or "unlovable" appearing literally in the text.

### 2.2 `stemsFrom` can branch — one Situation can trigger multiple AutomaticThoughts that stem from different CoreBeliefs

`S1` triggers AT1 through AT5 (5 automatic thoughts from one situation), and
those 5 thoughts split across **two different** `stemsFrom` targets (CB1 vs
CB2). This is a fan-out, not a 1:1 chain. The Tier-A anchor prompt (v7.1 §3.4.6,
the `AutomaticThought` anchor family) must evaluate `stemsFrom` **independently
per AutomaticThought**, never assume all ATs triggered by the same Situation
share one CoreBelief.

### 2.3 `stemsFrom` can point through an IntermediateBelief instead of directly to a CoreBelief

`AT8` ("I might slip up and start asking how he is") stems from `IB3` (the
caretaking rule), **not** directly from a CoreBelief — the gold file's
`v4_rules_applied` note states:

> *"AT8 stems from IB3 not CB directly — the slip-up fear is driven by the
> strength of the rule, not the belief itself."*

**This confirms `AutomaticThought stemsFrom` already allows both `CoreBelief`
and `IntermediateBelief` as valid objects** (v7.1 §3.4.6 anchor family for
`AutomaticThought` already lists `stemsFrom → CoreBelief`; this addendum adds
`IntermediateBelief` as an equally valid target). Update `ANCHOR_FAMILIES`:

```python
"AutomaticThought": [
    ("leadsTo", "Reaction", <hint+intensity>),
    ("stemsFrom", "CoreBelief", <hint>),
    ("stemsFrom", "IntermediateBelief", <hint: "this thought reflects the strength/demand of this rule, not the belief itself">),
    ("associatedWith", "Problem", <fallback hint>),
    ("hasAdaptiveResponse", "AdaptiveResponse", <hint>),
],
```

Add to `ALLOWED_SIGNATURES`:
```python
("stemsFrom", "AutomaticThought", "IntermediateBelief")
```

The judgment rule for the extraction prompt: if the thought's content is driven
by the *demand/standard itself* ("I might fail to follow my rule"), target the
`IntermediateBelief`; if it reflects the *underlying identity claim* ("there's
something wrong with me"), target the `CoreBelief`.

### 2.4 `IntermediateBelief` can arise from a single CoreBelief in bulk (1-to-many `givesRiseTo`)

All three IntermediateBeliefs in the gold file (`IB1`, `IB2`, `IB3`) arise from
the **same** CoreBelief (`CB1`, worthless). This is already valid per v7.1's
edge cardinality (no 1:1 constraint was ever implied), but the gold file proves
this fan-out is common and the extraction prompt should not artificially cap
the number of `givesRiseTo` edges from one CoreBelief.

### 2.5 `reinforces` confirmed strictly Tier-B / wide-window, with a "note-flagged" status

The gold file marks both `reinforces` edges with an explicit note:
*"Stage-3 wide-window LLM pass only."* This is full confirmation of v7.1 §3.4.8
— no change needed, but it's worth adding the literal note text as a
documentation string on the `REINFORCES` constant in `ontology.py`:

```python
REINFORCES = ("reinforces", "Reaction", "CoreBelief")
# NOTE: Stage-3 wide-window LLM pass only. Never extracted per-turn (Tier A).
# Absence of a reinforces edge is clinically informative; do not fabricate.
```

### 2.6 `Goal targetsProblem Problem` — direction confirmed

`G1 --targetsProblem--> P3`. This matches v7.1 §3.4.3 exactly (Goal → Problem
direction). No change; gold file is a direct confirmation example for the
test fixture (§3 below).

### 2.7 `associatedWith` correctly unused when the full chain is present

The gold file's exclusions explicitly note `associatedWith` was *not* used
because a complete `Problem → Situation → AutomaticThought` chain existed for
every AT. This confirms the v7.1 §3.4.2 fallback semantics: `associatedWith` is
a **fallback only** — the extraction prompt must attempt the full chain first
and only fall back to `associatedWith` when no `Situation` can be identified.
No schema change; this is a prompt-priority confirmation.

### 2.8 Intervention-technique `other` requires `techniqueLabel`, confirmed with real values

Two Interventions in the gold file use `technique: "other"` with populated
`techniqueLabel`:

```
I1: technique=other, techniqueLabel="laddering / downward arrow"
I2: technique=other, techniqueLabel="psychoeducation"
```

This is a direct confirmation of v7.1 §3.1.6 / §3.3 rule 4 (techniqueLabel only
populated when technique=other). Useful as a few-shot example in
`prompts.py`'s property-classification prompt — "laddering" and
"psychoeducation" are *not* in the CACTUS-12 enum and must fall through to
`other`, not be force-fit into the nearest technique.

### 2.9 Intellectual disavowal does not negate extraction

The gold file's exclusions list documents a case where the client says *"I
don't think I'm worthless"* (turn 13) shortly after the CoreBelief surfaced —
and the extraction **keeps** CB1 anyway, with the note:

> *"Turn 13 is intellectual disavowal — Beck explicitly notes this is normal
> when a core belief first surfaces. Does not negate extraction."*

**Action for `prompts.py`:** add this as an explicit few-shot rule in the
CoreBelief extraction/merge prompt — a later surface-level denial of a belief
that was clearly evidenced earlier should NOT cause the node to be deleted,
merged away, or downgraded. This is a clinically important nuance: surface
disavowal right after a core belief surfaces is expected, not disconfirming.

### 2.10 Therapist-attributed language must not be misattributed to the client

The gold file's exclusions explicitly walks back a prior draft that extracted
a `Reaction` ("heartbroken") from the therapist's word ("devastating," turn 4)
rather than the client's own words. The corrected `R3` instead uses the
client-affirmed "icky/uncomfortable" from turns 34–36.

**Action for `prompts.py`:** reinforce the existing `SPEAKER_PRIOR` rule (v7.1
§3.5) — content nodes for `Reaction`/`AutomaticThought`/`CoreBelief` etc. must
be grounded in the **client's own words or explicit affirmation**, never in a
therapist's framing language alone, even when the client gives a minimal
acknowledgement like "yeah." The gold file's R3 is a borderline case the
extraction system should be able to handle: client says "yeah" to the
therapist's framing AND elaborates further (turn 35) — the elaboration is what
justifies extraction, not the bare "yeah."

---

## 3. New test fixture: gold-file parity test

Add `demo1_ground_truth_v4_flat.json` to the test fixtures directory
(`tests/fixtures/demo1_ground_truth_v4_flat.json`) and add a new test:

**`tests/test_ontology_gold_parity.py`**

```python
def test_gold_file_loads_under_v4_flat_schema():
    """Every node label, every property key/value, and every edge predicate
    in the gold file must validate against ontology.py's NODE_CLASSES,
    property enums, and ALLOWED_SIGNATURES."""
    # Load fixture, assert:
    #  - every node["label"] in CONTENT_LABELS ∪ {Client, Session}
    #  - every attrs key/value pair passes apply_gating_constraints without mutation
    #  - every edge (predicate, source.label, target.label) in ALLOWED_SIGNATURES
    #  - CoreBelief→influencesPerceptionOf→Situation does NOT appear anywhere
    #  - reinforces edges only target CoreBelief from Reaction
    #  - techniqueLabel present iff technique == "other"

def test_gold_file_stemsFrom_targets_both_classes():
    """Confirms AT->stemsFrom->CoreBelief AND AT->stemsFrom->IntermediateBelief
    both appear in the gold file (AT8 -> IB3), proving ANCHOR_FAMILIES allows both."""

def test_gold_file_multiple_corebeliefs_distinct_categories():
    """CB1 (worthless) and CB2 (unlovable) are both domain=self but different
    category — confirms merge logic must not collapse across categories."""
```

This fixture becomes the **primary regression test** for the TurnPipeline once
Tier A/Tier B are implemented: replaying the 45-turn transcript through the live
pipeline and diffing the resulting graph against this gold file (node-class
recall, edge-predicate recall) is the most direct CBT-correctness check available
for this project. Recommend wiring this as `test_turn_pipeline_gold_replay.py`
once `TurnPipeline` exists — not required for the ontology layer alone, but
flagged here so it isn't forgotten.

---

## 4. Summary of `ontology.py` diffs required

| Change | Location | Type |
|---|---|---|
| Remove/confirm-absent `CoreBelief→influencesPerceptionOf→Situation` | `ANCHOR_FAMILIES["CoreBelief"]`, `ALLOWED_SIGNATURES` | hard removal |
| Confirm in `DISJOINT_RULES` | `DISJOINT_RULES` | enforcement check |
| Add `stemsFrom → IntermediateBelief` as valid AT target | `ANCHOR_FAMILIES["AutomaticThought"]`, `ALLOWED_SIGNATURES` | addition |
| Document `reinforces` Tier-B-only with inline comment | `ontology.py` constant docstring | documentation only |

## 5. Summary of `prompts.py` additions required

| Rule | Prompt affected |
|---|---|
| Don't merge CoreBeliefs across different `category` values | MERGE step (Tier A step 4) |
| `stemsFrom` evaluated per-AT independently, can fan out to different CoreBeliefs | EDGE_ANCHOR_PROMPT (AutomaticThought family) |
| `stemsFrom → IntermediateBelief` when thought reflects rule-strength, not identity | EDGE_ANCHOR_PROMPT (AutomaticThought family) |
| `givesRiseTo` fan-out from one CoreBelief is normal, don't cap | EDGE_ANCHOR_PROMPT (CoreBelief family) |
| `associatedWith` only as fallback after attempting full chain | EXTRACT_PROMPT / EDGE_ANCHOR_PROMPT |
| `technique=other` + populated `techniqueLabel` few-shot (laddering, psychoeducation) | PROPERTY_PROMPT (Intervention) |
| Intellectual disavowal after a CoreBelief surfaces does not negate extraction | PROPERTY_PROMPT / MERGE step (CoreBelief) |
| Ground Reaction/AT/CoreBelief in client's own words/affirmation, not therapist framing | EXTRACT_PROMPT (speaker grounding) |

---

## 6. Acceptance criteria (additions to v7.1 §10)

- `test_gold_file_loads_under_v4_flat_schema` passes against
  `demo1_ground_truth_v4_flat.json`.
- `ANCHOR_FAMILIES["AutomaticThought"]` includes both `stemsFrom→CoreBelief` and
  `stemsFrom→IntermediateBelief`.
- `CoreBelief→influencesPerceptionOf→Situation` is absent from
  `ALLOWED_SIGNATURES` and present in `DISJOINT_RULES`.
- The MERGE step's category-aware dedup logic is unit-tested with the CB1/CB2
  gold pair (same domain, different category → must remain two nodes).

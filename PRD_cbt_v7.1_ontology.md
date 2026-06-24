# PRD: CBT Knowledge-Graph Chatbot System — v7.1 (Ontology-Complete)

**Version:** 7.1
**Status:** Ready for implementation
**Supersedes:** v7.0 (adds the complete, exhaustive ontology reference — §3)
**Model:** `qwen3.5-nothink` via Ollama native API
**Stack:** Python · FastAPI · Gradio · Ollama · Neo4j (optional) / in-memory

> This version embeds the **entire V4_flat ontology** as the authoritative §3.
> Every node class, every property, every enum value with its gloss, every edge,
> every constraint, and the class hierarchy are specified here verbatim. §3 is the
> single source of truth; `ontology.py` must match it exactly and
> `test_ontology.py` must assert it. Architecture (§1, §2, §4–§12) is unchanged
> from v7.0 and summarized at the end.

---

## 0. Global Rules

1. **ONE ontology only: V4_flat** (this document, §3). Anything not in §3 is deleted.
2. **CBT correctness is the priority.** Faithful to Beck + CACTUS via V4_flat.
3. **Reuse V4_flat prompts.** Port extraction / property / edge prompts as-is.
4. **Dependency rule:** only `factory.py` imports concretes.
5. **Two parts, two tabs, one graph backend, one ontology.**

---

# 3. THE ONTOLOGY (Complete, Authoritative)

`ontology.py` is a verbatim port of `cbt_ontology_v4_flat.py`. The constant names
below are the exact symbols that must exist in `ontology.py`.

## 3.0 Class hierarchy (TBox)

`CLASS_HIERARCHY: dict[str, str | None]` — every class and its single parent.
The graph is **flat**: content nodes carry only the abstract family label; the
former subclass discriminator lives in a property. No subclass leaf labels.

```
owl:Thing
├── Provenance
│   └── Utterance
├── Client                          (top-level anchor)
├── SessionStructure
│   ├── Session
│   ├── Problem
│   ├── Goal
│   ├── Intervention
│   └── Homework
└── CognitiveModel
    ├── CoreBelief
    ├── IntermediateBelief
    ├── Situation
    ├── AutomaticThought
    ├── Reaction
    └── AdaptiveResponse
```

`CLASS_HIERARCHY` literal:

```python
CLASS_HIERARCHY = {
    "OWL_Thing": None,
    "Provenance": "OWL_Thing",
    "Utterance": "Provenance",
    "SessionStructure": "OWL_Thing",
    "Session": "SessionStructure",
    "Client": "OWL_Thing",
    "Problem": "SessionStructure",
    "Goal": "SessionStructure",
    "Intervention": "SessionStructure",
    "Homework": "SessionStructure",
    "CognitiveModel": "OWL_Thing",
    "CoreBelief": "CognitiveModel",
    "IntermediateBelief": "CognitiveModel",
    "Situation": "CognitiveModel",
    "AutomaticThought": "CognitiveModel",
    "Reaction": "CognitiveModel",
    "AdaptiveResponse": "CognitiveModel",
}
```

**13 node classes total.** 3 are scaffold (`Utterance`, `Client`, `Session`) and
are **not extracted** from speech. 10 are content classes (`EXTRACT_CLASSES`).

`CONTENT_LABELS` = the 10 content classes (every class except Client/Session/Utterance).

---

## 3.1 Node classes — full specification

Each class below lists: its **definition** (`CLASS_DEFINITIONS`, used in the
extraction prompt), every **property** (name · type · required? · enum · gloss ·
constraints), its **ID prefix** (`ID_PREFIX`, used for export node ids), its
**text property** (`TEXT_PROP`, the property holding the node's main text), the
**speaker(s)** that typically produce it (`SPEAKER_PRIOR`), and its **extraction
timing** (Tier A per-turn vs Tier B session-level — see §4).

### 3.1.1 `Utterance` — scaffold (provenance)

Not extracted. Created once per turn as provenance.

| Property | Type | Required | Notes |
|---|---|---|---|
| `text` | string | yes | verbatim transcript span |
| `speaker` | enum `therapist \| client` | yes | |
| `turnIndex` | integer | yes | unique **within a Session** (see `inSession`) |
| `timestamp` | string | optional | |

ID prefix: `utt`. Multi: yes.

### 3.1.2 `Client` — scaffold (anchor)

Not extracted. One per graph. No required fields. ID prefix: `client`. Multi: no.

### 3.1.3 `Session` — scaffold

Not extracted. One per graph.

| Property | Type | Required | Enum |
|---|---|---|---|
| `sessionNumber` | integer | optional | |
| `sessionType` | enum | yes | `evaluation \| therapy` |
| `date` | string | optional | |
| `duration` | string | optional | |

ID prefix: `session`. Multi: no.

### 3.1.4 `Problem` — content

**Definition:** A GENERAL, ongoing area of difficulty — the kind of thing that
would be a heading on a session agenda ("trouble making friends",
"procrastination"). A recurring theme, NOT a single moment, NOT a mood. Test:
would it appear as a session heading? → Problem. A Problem `manifestsAs` specific
Situations.

| Property | Type | Required | Enum |
|---|---|---|---|
| `description` | string | yes | — |
| `domain` | enum | yes | `academic \| work \| social \| family \| financial \| health \| other` |

`domain` glosses (`SUBCLASS_GLOSS["Problem"]`):
- `academic` — school, study, exams, grades
- `work` — job, career, workplace
- `social` — friends, peers, dating, social situations
- `family` — parents, siblings, partner, children
- `financial` — money, debt, finances
- `health` — physical or mental health (incl. depression/anxiety)
- `other` — cross-domain, unclear, or fits no other category

ID prefix: `prob`. Text prop: `description`. Speaker: client. Timing: **Tier B**
(session-level — recurring theme). Multi: yes.

### 3.1.5 `Goal` — content

**Definition:** A desired outcome — what the client wants instead of the problem.
Forward-facing and positive.

| Property | Type | Required |
|---|---|---|
| `statement` | string | yes |

ID prefix: `goal`. Text prop: `statement`. Speaker: client or therapist. Timing:
**Tier B**. Multi: yes.

### 3.1.6 `Intervention` — content

**Definition:** A therapeutic technique the therapist applies. Spans many turns.
Guided discovery / Socratic questioning is the general style — do NOT extract it
as a technique.

| Property | Type | Required | Enum |
|---|---|---|---|
| `description` | string | yes | condensed one-sentence summary |
| `technique` | enum | yes | **CACTUS-12** (see §3.2 `TECHNIQUES`) |
| `techniqueLabel` | string | optional | **only when** `technique = other` (free text) |

ID prefix: `intv`. Text prop: `description`. Speaker: therapist. Timing: **Tier B**.
Multi: yes.

### 3.1.7 `Homework` — content

**Definition:** A between-session task the therapist assigns the client to do
before the next session.

| Property | Type | Required | Enum |
|---|---|---|---|
| `taskDescription` | string | yes | — |
| `taskType` | enum | yes | `thoughtRecord \| behavioralExperiment \| activityScheduling \| copingCard \| skillsPractice \| reading \| other` |
| `isOptional` | boolean | yes | default `false` |

`taskType` glosses (`HOMEWORK_TASKTYPES`):
- `thoughtRecord` — record situations/thoughts/feelings (e.g. a thought diary)
- `behavioralExperiment` — test a prediction or belief through a real-world action
- `activityScheduling` — schedule and carry out planned activities
- `copingCard` — make/use a card with a coping statement
- `skillsPractice` — practise a specific skill (relaxation, assertiveness, etc.)
- `reading` — read assigned material (bibliotherapy)
- `other` — any task outside the categories above

`isOptional` rule: `true` only when the therapist explicitly frames it as optional
("if you want to", "you don't have to"); otherwise `false`.

ID prefix: `hw`. Text prop: `taskDescription`. Speaker: therapist. Timing: **Tier B**.
Multi: yes.

### 3.1.8 `CoreBelief` — content

**Definition:** An ABSOLUTE, global belief about the self, the world, or other
people, stated with no condition — e.g. "I am worthless", "I am unlovable",
"people cannot be trusted". It is NOT a rule and NOT a condition. If the text
contains "I must / I should / I have to" or "if … then …", it is an
IntermediateBelief, not a CoreBelief. If it is tied to one specific moment, it is
an AutomaticThought.

| Property | Type | Required | Enum |
|---|---|---|---|
| `content` | string | yes | — |
| `domain` | enum | yes | `self \| world \| others` |
| `category` | enum | optional | `helpless \| unlovable \| worthless` — **only when `domain = self`**, else null (Beck Fig 14.1) |

`domain` glosses (`SUBCLASS_GLOSS["CoreBelief"]`):
- `self` — a belief about oneself (incl. lovability/worth, even if it mentions relationships — "no one could love me" is about the SELF)
- `world` — a belief about the world ("the world is dangerous")
- `others` — a belief about other people in general ("people are cruel")

`category` glosses (`SELF_CB_CATEGORIES`, self-directed only):
- `helpless` — incapable, ineffective, powerless, a failure
- `unlovable` — unwanted, rejected, unworthy of relationships
- `worthless` — bad, immoral, deserving of bad things

ID prefix: `cb`. Text prop: `content`. Speaker: client. Timing: **Tier B**
(laddered across turns). Multi: yes.

### 3.1.9 `IntermediateBelief` — content

**Definition:** A conditional or instrumental belief sitting between core beliefs
and automatic thoughts: a RULE ("I must always do my best"), an ASSUMPTION ("if I
ask for help, people think I'm incompetent"), or an ATTITUDE ("it's terrible to
fail"). Marked by "must / should / have to" or "if … then …". It is NOT an
absolute identity claim like "I am worthless" (that is a CoreBelief).

| Property | Type | Required | Enum |
|---|---|---|---|
| `content` | string | yes | — |
| `subtype` | enum | yes | `attitude \| rule \| assumption` |

`subtype` glosses (`SUBCLASS_GLOSS["IntermediateBelief"]`):
- `attitude` — an evaluation ("It's terrible to fail", "Asking for help is weak")
- `rule` — a demand or standard ("I must always do my best")
- `assumption` — a conditional if-then ("If I ask for help, people think I'm incompetent")

ID prefix: `ib`. Text prop: `content`. Speaker: client. Timing: **Tier B**. Multi: yes.

### 3.1.10 `Situation` — content

**Definition:** A SINGLE, concrete, time-bound moment that triggered a specific
automatic thought. The first link of a Situation→AutomaticThought→Reaction chain.
Test: can you attach ONE specific automatic thought to this exact moment? → Situation.

| Property | Type | Required | Enum |
|---|---|---|---|
| `description` | string | yes | — |
| `kind` | enum | yes | `externalSituation \| thoughtStream \| image \| emotion \| behavior \| physiological` |
| `temporality` | enum | optional | `past \| present \| anticipated` — **only with an explicit time marker**, else null |

`kind` is the trigger CHANNEL only — carries NO time meaning. Glosses (`SITUATION_KINDS`):
- `externalSituation` — a real external event/circumstance (incl. a recalled past event)
- `thoughtStream` — a vague worry-spiral; the extracted thought is its conclusion
- `image` — a mental picture that arose unbidden
- `emotion` — an emotion that itself triggered the thought (first link in the chain)
- `behavior` — an action that triggered the thought (first link in the chain)
- `physiological` — a body sensation that triggered the thought (first link in the chain)

`kind` rules: `behavior`/`physiological` as a `kind` = FIRST link in the chain
only; if it *follows* a thought it is a `Reaction`, not a `Situation`.
`temporality` is the ONLY property carrying time.

**Situation vs Problem:** Situation = ONE concrete moment that triggers a specific
automatic thought. Problem = a GENERAL recurring area of difficulty. Link:
`Problem manifestsAs Situation`.

ID prefix: `sit`. Text prop: `description`. Speaker: client. Timing: **Tier A**
(per-turn safe). Multi: yes.

### 3.1.11 `AutomaticThought` — content

**Definition:** A spontaneous, situation-specific thought tied to ONE moment —
e.g. "he didn't text back, he's angry at me". It is NOT a general rule ("I must …"
= IntermediateBelief) and NOT an absolute identity claim ("I am worthless" =
CoreBelief). Keep emotions OUT of the content (a feeling is a Reaction).

| Property | Type | Required | Enum |
|---|---|---|---|
| `content` | string | yes | — |
| `modality` | enum | yes | `verbal \| image` (default `verbal`) |
| `distortionType` | enum | optional | **PatternReframe-10** + `none` |

`modality` glosses: `verbal` = a worded thought; `image` = a mental picture.

`distortionType` glosses (`DISTORTION_TYPES`):
- `allOrNothing` — black-and-white, nothing in between ("I'm a total failure")
- `catastrophizing` — assuming the worst outcome ("my life is ruined")
- `discountingPositive` — positives don't count ("I only passed because it was easy")
- `fortuneTelling` — predicting a negative outcome ("I know I'll fail")
- `labeling` — judging character from one action ("I'm stupid")
- `mentalFiltering` — only the negatives matter
- `mindReading` — assuming others' negative thoughts ("she thinks I'm boring")
- `overgeneralization` — broad conclusion from one event ("I always mess up")
- `personalization` — excessive self-blame ("the team failed because of me")
- `shouldStatements` — rigid demands ("I should be able to handle this")
- `none` — the thought is realistic / not distorted

`distortionType` rule: use `none` if the thought is accurate or no pattern fits —
do not force one.

ID prefix: `at`. Text prop: `content`. Speaker: client. Timing: **Tier A**. Multi: yes.

### 3.1.12 `Reaction` — content

**Definition:** The client's response to an automatic thought — a feeling, an
action/avoidance, or a body sensation.

| Property | Type | Required | Enum |
|---|---|---|---|
| `content` | string | yes | — |
| `channel` | enum | yes | `emotional \| behavioral \| physiological` |
| `valence` | enum | optional | `positive \| negative` — **only when `channel = emotional`**, else null |

`channel` glosses (`SUBCLASS_GLOSS["Reaction"]`):
- `emotional` — a feeling (anxious, ashamed, relieved, sad, lonely)
- `behavioral` — an action or avoidance (stayed in bed, avoided the call, cried)
- `physiological` — a body sensation (heart racing, chest tight, couldn't breathe)

`valence` rule: lexicon-derived (V4_flat uses a Thai emotion list, NOT the LLM).
For an English demo, supply an English emotion lexicon or use the LLM with the
explicit positive/negative gloss — **document the choice** (see §4 note).

ID prefix: `react`. Text prop: `content`. Speaker: client. Timing: **Tier A** for
the node; the **`reinforces`** edge it can participate in is **Tier B only**. Multi: yes.

### 3.1.13 `AdaptiveResponse` — content

**Definition:** A BALANCED, realistic response developed to counter an automatic
thought (the product of reframing). Balanced, NOT merely positive (Beck p.171).
Only when genuinely reached — a therapist suggestion the client does not
internalise is NOT one.

| Property | Type | Required |
|---|---|---|
| `content` | string | yes |

ID prefix: `adapt`. Text prop: `content`. Speaker: client or therapist. Timing:
**Tier B** (multi-turn product of reframing). Multi: yes.

---

## 3.2 Property-value enums (complete, with glosses)

These are the exact constants `ontology.py` must export. They are the **only**
legal values; extraction and the query engine reject anything outside them.

```python
PROBLEM_DOMAINS     = ("academic","work","social","family","financial","health","other")
CORE_BELIEF_DOMAINS = ("self","world","others")
IB_SUBTYPES         = ("attitude","rule","assumption")
REACTION_CHANNELS   = ("emotional","behavioral","physiological")
```

`GROUP_KEY_PROP` — maps the discriminator-bearing class to the property name that
holds its discriminator (set during extraction):

```python
GROUP_KEY_PROP = {
    "Problem": "domain",
    "CoreBelief": "domain",
    "IntermediateBelief": "subtype",
    "Reaction": "channel",
}
```

`SITUATION_KINDS`, `DISTORTION_TYPES`, `TECHNIQUES`, `SELF_CB_CATEGORIES`,
`HOMEWORK_TASKTYPES` — full gloss dicts as written in §3.1 above. The complete
`TECHNIQUES` dict (CACTUS-12 + `other`):

```python
TECHNIQUES = {
  "efficiencyEvaluation": "is this thought actually useful in real life?",
  "pieChartTechnique": "break down contributing factors visually (excessive self-blame)",
  "alternativePerspective": "how would someone else see this situation?",
  "decatastrophizing": "examine the real probability of the feared outcome",
  "prosAndConsAnalysis": "list advantages and disadvantages of a thought",
  "evidenceBasedQuestioning": "what evidence supports / goes against this thought?",
  "realityTesting": "does this thought actually match reality?",
  "continuumTechnique": "place a judgment on a 0-100 scale, not all-or-nothing",
  "changingRulesToWishes": "turn \"I must/should\" into \"I'd prefer/wish\"",
  "behaviorExperiment": "plan a real-world test of a belief or prediction",
  "problemSolvingSkillsTraining": "teach step-by-step problem-solving",
  "systematicExposure": "graded, repeated approach to a feared situation",
  "other": "anything outside the 12 (record the name in techniqueLabel)",
}
```

---

## 3.3 Property-population constraints (gating)

These conditional rules are **part of the ontology** and must be enforced wherever
properties are written (Tier A property step, the editor in Part 2, the query
validator):

1. `CoreBelief.category` is populated **only when** `CoreBelief.domain == "self"`. Else null.
2. `Reaction.valence` is populated **only when** `Reaction.channel == "emotional"`. Else null.
3. `Situation.temporality` is populated **only with an explicit time marker** in the text. Else null.
4. `Intervention.techniqueLabel` is populated **only when** `Intervention.technique == "other"`. Else absent.
5. `AutomaticThought.modality` defaults to `verbal` when unspecified.
6. `Homework.isOptional` defaults to `false` when unspecified.
7. `AutomaticThought.distortionType` may be `none`; do not force a distortion.

---

## 3.4 Edges — full registry

Every edge is `(subject_label, predicate, object_label)`. Edge groups, their
**hints** (used in the Stage-3 anchor prompt), the optional **edge property**, the
**extraction timing**, and the **Neo4j relationship type** (`REL_TYPE`) follow.

### 3.4.1 Cognitive chain (LLM-extracted)

| Subject | Predicate | Object | Edge prop | Hint | Timing | REL_TYPE |
|---|---|---|---|---|---|---|
| `CoreBelief` | `givesRiseTo` | `IntermediateBelief` | — | this core belief underlies that rule/attitude/assumption | Tier A | `GIVES_RISE_TO` |
| `IntermediateBelief` | `influencesPerceptionOf` | `Situation` | — | this belief shapes how the client perceived that situation | Tier A | `INFLUENCES_PERCEPTION_OF` |
| `Situation` | `triggers` | `AutomaticThought` | — | this situation sparked that automatic thought | Tier A | `TRIGGERS` |
| `AutomaticThought` | `leadsTo` | `Reaction` | `reportedIntensity?` | the reaction that followed this thought; add `reportedIntensity` ONLY if the client states a strength ("very anxious"/"8/10") | Tier A | `LEADS_TO` |
| `AutomaticThought` | `stemsFrom` | `CoreBelief` | — | this thought reflects/derives from that core belief (downward-arrow / ladder) | Tier A | `STEMS_FROM` |
| `Reaction` | `reinforces` | `CoreBelief` | — | reaction feeds back to maintain/strengthen the belief | **Tier B only** (wide-window; never per-turn) | `REINFORCES` |
| `Reaction` | `becomesSituation` | `Situation` | — | this reaction itself became the trigger for a new thought (cascade) — only if clearly shown | Tier B | `BECOMES_SITUATION` |
| `AutomaticThought` | `hasAdaptiveResponse` | `AdaptiveResponse` | — | the balanced response that answers this thought | **Tier B** | `HAS_ADAPTIVE_RESPONSE` |

### 3.4.2 Cross-layer hinge (LLM-extracted)

| Subject | Predicate | Object | Hint | Timing | REL_TYPE |
|---|---|---|---|---|---|
| `AutomaticThought` | `associatedWith` | `Problem` | FALLBACK: the problem this thought is tied to — use when no Situation routes it | Tier A | `ASSOCIATED_WITH` |
| `Intervention` | `appliedTo` | `AutomaticThought` | this technique examined that thought | Tier B | `APPLIED_TO` |
| `Intervention` | `appliedTo` | `IntermediateBelief` | this technique examined that rule/assumption | Tier B | `APPLIED_TO` |
| `Intervention` | `appliedTo` | `CoreBelief` | this technique directly challenged that core belief | Tier B | `APPLIED_TO` |
| `Intervention` | `appliedTo` | `Problem` | this technique worked on that problem | Tier B | `APPLIED_TO` |
| `Intervention` | `produces` | `AdaptiveResponse` | the transcript shows this technique GENERATING that balanced response | Tier B | `PRODUCES` |

### 3.4.3 Problem / Goal / Homework (LLM-extracted)

| Subject | Predicate | Object | Hint | Timing | REL_TYPE |
|---|---|---|---|---|---|
| `Problem` | `manifestsAs` | `Situation` | this general problem shows up as that specific moment | Tier A | `MANIFESTS_AS` |
| `Goal` | `targetsProblem` | `Problem` | this goal addresses that problem (Goal → Problem direction) | Tier B | `TARGETS_PROBLEM` |
| `Homework` | `targets` | `Problem` | the homework works on this problem | Tier B | `TARGETS` |
| `Homework` | `targets` | `AutomaticThought` | the homework (e.g. thought record) works on this thought | Tier B | `TARGETS` |
| `Homework` | `targets` | `IntermediateBelief` | the homework (e.g. experiment) tests this rule/assumption | Tier B | `TARGETS` |
| `Homework` | `targets` | `CoreBelief` | the homework works directly on this core belief | Tier B | `TARGETS` |

### 3.4.4 Structure (deterministic — no LLM)

| Subject | Predicate | Object | REL_TYPE |
|---|---|---|---|
| `Client` | `hasSession` | `Session` | `HAS_SESSION` |
| `Session` | `hasProblem` | `Problem` | `HAS_PROBLEM` |
| `Session` | `hasIntervention` | `Intervention` | `HAS_INTERVENTION` |
| `Session` | `hasHomework` | `Homework` | `HAS_HOMEWORK` |

### 3.4.5 Provenance (deterministic)

| Subject | Predicate | Object | REL_TYPE |
|---|---|---|---|
| every content node | `evidencedBy` | `Utterance` | `EVIDENCED_BY` |
| `Utterance` | `inSession` | `Session` | `IN_SESSION` |

`DETERMINISTIC_PREDICATES = {hasSession, hasProblem, hasIntervention, hasHomework, evidencedBy, inSession}`.

### 3.4.6 `ANCHOR_FAMILIES` (subject-anchored extraction map)

The Stage-3 / Tier-A edge prompt issues **one call per subject node**, covering
all that subject's families at once. The literal map:

```python
ANCHOR_FAMILIES = {
  "Situation":          [("triggers","AutomaticThought", <hint>)],
  "AutomaticThought":   [("leadsTo","Reaction", <hint+intensity>),
                         ("stemsFrom","CoreBelief", <hint>),
                         ("associatedWith","Problem", <fallback hint>),
                         ("hasAdaptiveResponse","AdaptiveResponse", <hint>)],
  "CoreBelief":         [("givesRiseTo","IntermediateBelief", <hint>)],
  "IntermediateBelief": [("influencesPerceptionOf","Situation", <hint>)],
  "Reaction":           [("becomesSituation","Situation", <hint>)],
  "Problem":            [("manifestsAs","Situation", <hint>)],
  "Goal":               [("targetsProblem","Problem", <hint>)],
  "Homework":           [("targets","Problem", <hint>),
                         ("targets","AutomaticThought", <hint>),
                         ("targets","IntermediateBelief", <hint>),
                         ("targets","CoreBelief", <hint>)],
  "Intervention":       [("appliedTo","AutomaticThought", <hint>),
                         ("appliedTo","IntermediateBelief", <hint>),
                         ("appliedTo","CoreBelief", <hint>),
                         ("appliedTo","Problem", <hint>),
                         ("produces","AdaptiveResponse", <hint>)],
}
REINFORCES = ("reinforces", "Reaction", "CoreBelief")   # wide-window pass only
```

### 3.4.7 Edge signatures, disjointness, repair

```python
ALLOWED_SIGNATURES = frozenset(
    [(p, subj, o) for subj, fams in ANCHOR_FAMILIES.items() for (p, o, _h) in fams]
    + [REINFORCES]
)

# predicate -> set of allowed object labels (for repair re-pointing)
PREDICATE_OBJECTS = {p: {o for (_p,_s,o) in ALLOWED_SIGNATURES if _p==p} for p,_,_ in ALLOWED_SIGNATURES}

# Hard disjointness — must never appear regardless of predicate:
DISJOINT_RULES = [
  ("AutomaticThought", "*", "AutomaticThought"),          # no AT→AT edges
  ("CoreBelief", "influencesPerceptionOf", "Situation"),  # skip-level dropped
  ("Intervention", "appliedTo", "Goal"),                  # goals are outcomes, not targets
]
```

### 3.4.8 `reinforces` — special timing note

`reinforces` (Reaction → CoreBelief) is **wide-window only** and produced **only**
by the dedicated Tier-B pass, **never** by the subject-anchored Tier-A pass.
Absence of a `reinforces` edge is clinically informative — do not fabricate it.

---

## 3.5 Speaker priors & extract-class list

```python
EXTRACT_CLASSES = ["Problem","Goal","Intervention","Homework","CoreBelief",
                   "IntermediateBelief","Situation","AutomaticThought",
                   "Reaction","AdaptiveResponse"]   # Client/Session/Utterance are scaffold

SPEAKER_PRIOR = {
  "client":    ["Situation","AutomaticThought","Reaction","CoreBelief",
                "IntermediateBelief","Problem","Goal","AdaptiveResponse"],
  "therapist": ["Intervention","Homework","Goal","AdaptiveResponse"],
}
```

`ID_PREFIX` (export node ids) and `TEXT_PROP` (main-text key per class):

```python
ID_PREFIX = {"Client":"client","Session":"session","Problem":"prob","Goal":"goal",
  "Intervention":"intv","Homework":"hw","CoreBelief":"cb","IntermediateBelief":"ib",
  "Situation":"sit","AutomaticThought":"at","Reaction":"react","AdaptiveResponse":"adapt"}

# TEXT_PROP: Problem/Situation -> description; Goal -> statement;
# Homework -> taskDescription; Intervention -> description; all CognitiveModel
# content classes -> content.
```

---

## 3.6 Export shapes (both parts emit/consume these)

### 3.6.1 JSON export (V4_flat Stage-5 `build_json` shape)

```json
{
  "meta": {"schema_version":"ontology_v4_flat","transcript":"…","session_type":"therapy",
           "n_turns":N,"speaker_enum":["therapist","client"],"generated_by":"…"},
  "tbox_nodes": [{"id":"tbox_CoreBelief","label":"TBox","name":"CoreBelief"}, …],
  "tbox_edges": [{"type":"SUB_CLASS_OF","from":"tbox_CoreBelief","to":"tbox_CognitiveModel"}, …],
  "nodes": [
    {"id":"at_1","label":"AutomaticThought","parent":null,
     "properties":{"content":"…","modality":"verbal","distortionType":"catastrophizing"},
     "evidence":[12,13]}, …
  ],
  "edges": [
    {"type":"triggers","from":"sit_1","to":"at_1","evidence":[12]},
    {"type":"leadsTo","from":"at_1","to":"react_1","evidence":[13],"reportedIntensity":"8/10"}, …
  ],
  "summary_counts": {"nodes_total":N,"by_label":{…},"edges_total":M}
}
```

Flat rules: `label` is always the abstract family; `parent` is always `null`; the
discriminator lives inside `properties` (`domain`/`subtype`/`channel`).

### 3.6.2 Neo4j ABox shape (V4_flat `write_neo4j`)

```
(:Client:ABox {id})
(:Session:ABox {id, sessionType})
(:<Class>:ABox {id, <props…>, primaryLabel:"<Class>"})   one per content node
(:Utterance:ABox {id, turnIndex, speaker, text})
(content)-[:EVIDENCED_BY]->(:Utterance)
(:Utterance)-[:IN_SESSION]->(:Session)
(a:ABox)-[:<REL_TYPE>]->(b:ABox)   typed edges via REL_TYPE; LEADS_TO carries reportedIntensity
(:TBox {name}) with SUB_CLASS_OF;  (content)-[:IS_A]->(:TBox)
property indexes on Problem.domain, CoreBelief.domain, IntermediateBelief.subtype, Reaction.channel
```

**Part 1's `Neo4jGraphStore` must write this exact shape** so its output is
byte-compatible with the V4_flat batch export — that compatibility is what makes
Part 2's reader universal.

---

## 3.7 `test_ontology.py` must assert (acceptance for §3)

- 13 node classes exactly; 10 `EXTRACT_CLASSES` exactly.
- `CLASS_DEFINITIONS` covers every extract class (non-empty).
- `len(PROBLEM_DOMAINS)==7`, `CORE_BELIEF_DOMAINS=={self,world,others}`,
  `IB_SUBTYPES=={attitude,rule,assumption}`, `REACTION_CHANNELS` 3 values.
- `len(TECHNIQUES)==13` (CACTUS-12 + other), `len(DISTORTION_TYPES)==11` (PR-10 + none).
- `SELF_CB_CATEGORIES=={helpless,unlovable,worthless}`, `HOMEWORK_TASKTYPES` 7 values,
  `SITUATION_KINDS` 6 values.
- `ANCHOR_FAMILIES` covers the canonical chain tuples in §3.4.6.
- `REL_TYPE` maps every predicate used in §3.4; reverse map `PREDICATE_FROM_REL` round-trips.
- Gating constraints (§3.3) enforced by the node-write helper.

---

# 4. Part 1 — Therapy Chatbot (pipeline summary)

Unchanged from v7.0. The per-turn extraction is a **two-tier** design that mirrors
V4_flat's batch stages and respects the §3.1/§3.4 timing column.

**Tier A (every client turn, background async):**
1. EXTRACT — V4_flat Stage-1 prompt (per-turn; ±2 context) → `[{label,text,group_key?}]`, filtered to `EXTRACT_CLASSES`, `SPEAKER_PRIOR` applied.
2. ATOMIZE — V4_flat Stage-1.2 prompt for `AutomaticThought`/`CoreBelief`/`IntermediateBelief` only (≤4 atomic).
3. PROPERTIES — V4_flat Stage-2.5 classifiers fill the §3.2 enums under §3.3 gating.
4. MERGE — string-Jaccard (>0.6) + occasional LLM tie-break against same-class found nodes; in-place upgrade or new node; attach `evidencedBy`.
5. EDGES (local) — V4_flat Stage-3 anchor prompt restricted to Tier-A predicates (§3.4 timing): `triggers, leadsTo(+reportedIntensity), stemsFrom, manifestsAs, givesRiseTo, influencesPerceptionOf, associatedWith`.

**Tier B (every `CONSOLIDATE_EVERY` turns + on reset, background):**
1. SESSION-LEVEL EXTRACT — V4_flat Stage-1.1 over the transcript for `CoreBelief, IntermediateBelief, Problem, Goal, Intervention, Homework, AdaptiveResponse` (+ Reaction recovery), then re-MERGE.
2. REINFORCES — V4_flat Stage-3 Pass B (Reaction × CoreBelief wide window).
3. REFRAME — `hasAdaptiveResponse`, `Intervention produces/appliedTo`.
4. STRUCTURE — deterministic `hasSession, hasProblem, hasIntervention, hasHomework, targetsProblem, targets`.

**Async loop:** generation never waits on extraction; per-session `asyncio.Lock`
guards graph writes; Tier B is detached. Latency unaffected.

**Phase gates (node-grounded):**
```python
PHASE_MINIMUMS = {
  "Exploration":   {"requires":["Problem"],                       "min_turns":2},
  "Technique":     {"requires":["AutomaticThought","Situation"],  "min_turns":5},
  "Consolidation": {"requires":["AdaptiveResponse"],              "min_turns":12},
}
```
`validate_phase` advances only if the graph holds ≥1 *found* node of each required
class and `turn_count ≥ min_turns`.

> **Reaction.valence note (per §3.1.12):** decide and document the English-lexicon
> vs LLM approach in `extract.py`; default to a small English emotion lexicon with
> LLM fallback so the §3.3 gating still holds.

---

# 5. Part 2 — Query Chatbot (summary)

- `GraphReader` returns a canonical `(list[GraphNode], list[GraphEdge])` from any
  source: `LiveGraphReader` (Part 1 store), `JsonGraphReader` (§3.6.1 export),
  `Neo4jGraphReader` (§3.6.2 ABox). All emit identical V4_flat-labeled output.
- NL query = parse → execute → answer. PARSE maps the question to a structured
  spec over the §3 vocabulary (classes, predicates, property enums); EXECUTE runs
  it deterministically over the loaded graph (filter + chain-walk); ANSWER narrates
  only from the result set with node ids + evidence turns.
- **Interactive graph (per the mockup):** click a node/edge → Inspector panel with
  all §3 properties; edit class/props/status; create nodes (class picker = §3.1)
  and edges (predicate picker = §3.4, validated against `ALLOWED_SIGNATURES`);
  delete; Save → exports §3.6.1 JSON. Part 1's panel is read-only (inspect only);
  Part 2 has full edit/create.

---

# 6–9. Infrastructure, API, UI, order (summary, unchanged from v7.0)

- `interfaces.py`: `GraphNode{node_id,label,props,status,evidence,turn_acquired}`,
  `GraphEdge{subject_id,predicate,object_id,props,status,evidence}`; protocols
  `Schema, GraphStore, Extractor, Generator, GraphReader`.
- `factory.py`: env wiring (`GRAPH_BACKEND, EXTRACTOR, GENERATOR, OLLAMA_MODEL,
  OLLAMA_HOST, EXTRACTION_TIMEOUT, CONSOLIDATE_EVERY, EXTRACT_FAST`).
- API: `/chat /reset /graph/{id}` (Part 1) · `/load_graph /query /graph_preview/{h}` (Part 2).
- UI: Tab 1 Therapy (read-only graph), Tab 2 Query (editable graph). Node colors:
  Session = green, Problem/Goal = blue, CognitiveModel = purple, Intervention/
  Homework = amber, missing = grey/dashed. Edges: found = solid green, placeholder = dashed.
- Build order: ontology → interfaces → graph_memory → prompts → extract(stub→TierA→TierB)
  → generate → therapy → graph_neo4j → graph_reader → query → factory/api/ui. `pytest`
  green after ontology, extract, therapy, reader.

---

# 10. Acceptance Criteria

- `ontology.py` matches §3 exactly; `test_ontology.py` (§3.7) green.
- Only §3 terms appear anywhere (no `presenting_problem`, no flat fields).
- A Part 1 session's export is schema-identical to a V4_flat batch export (§3.6).
- The same `query.py` answers over a live Part 1 graph and a downloaded JSON export.
- All §3.3 gating constraints hold on every write path (pipeline, editor, importer).
- `reinforces` / `AdaptiveResponse` never appear from a single turn (Tier B only).
- Chat latency unaffected by extraction.

---

# 11. Deferred

Heavy Stage-4 edge validation in the live loop; embedding-based merge; text-to-Cypher;
multi-session persistence; WebSocket graph push; subclass-typed (non-flat) graph.

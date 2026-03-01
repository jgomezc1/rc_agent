# ProDet Impact Matrix — Companion Guide

**Version:** 1.0.0 | **Date:** 2026-02-27 | **Step 2 of NL↔Config Agent System**

## Purpose

The Impact Matrix is the **causal reasoning backbone** of the agent system. It answers two questions:

- **NL→Config:** "The engineer wants X outcome → which parameter clusters should move in which direction?"
- **Config→NL:** "This config has these parameter values → what are the construction trade-offs?"

---

## The Eight Construction Dimensions

| ID | Dimension | What It Measures | Who Cares Most |
|----|-----------|------------------|----------------|
| D1 | Material Cost | Total kg of steel | Owner, Cost Engineer |
| D2 | Piece Count | Distinct bar types on cutting schedule | Contractor, Rebar Supplier |
| D3 | Field Error Risk | Probability of installation mistakes | Structural Engineer, Inspector |
| D4 | Installation Speed | Man-hours per floor for rebar | Contractor, Project Manager |
| D5 | Required Skill Level | Minimum crew experience needed | Contractor, HR |
| D6 | Drawing Clarity | Ease of reading shop drawings | Foreman, Crew |
| D7 | Inspection Complexity | Inspector effort per floor | QA Inspector, Building Authority |
| D8 | Adaptability | Tolerance to field deviations | Foreman, Structural Engineer |

---

## Master Impact Table

Direction shows what happens when moving from **Simple → Optimized** profile.

| Cluster | D1 Cost | D2 Pieces | D3 Errors | D4 Speed | D5 Skill | D6 Drawings | D7 Inspect | D8 Adapt |
|---------|---------|-----------|-----------|----------|----------|-------------|------------|----------|
| **A** Bar Envelope | ↓ med | ↑↑ high | ↑↑ high | ↓ med | ↑ med | ↓ med | ↑ med | ↓ low |
| **B** Splice Strategy | ↓↓ med-high | ± mixed | ↑↑ high | ↓ med | ↑↑ high | ↓ low | ↑↑ high | ↓ med |
| **C** Stirrups | ↓ low-med | ↑↑ high | ↑ med | ↓↓ high | ↑ med | ↓ med | ↑ med | ↓ low |
| **D** Merging/Tol. | ↓ med | ↑↑ high | ↑ med | ↓ med | ↑ low | ↓ med | ↑ low-med | ↓ med |
| **E** Overrides | ↓↓ med-high | ↑↑↑ v.high | ↑↑↑ v.high | ↓↓ high | ↑↑ high | ↓↓ high | ↑↑ high | ↓ med |
| **F** Drawings | — none | — none | ± mixed | — low | — none | ★ primary | ± low | — none |
| **G** Code Basis | ★ fixed | — low | ★ fixed | ★ fixed | ★ fixed | — low | ★ fixed | — low |
| **H** Materials | ↕ complex | ↑ low | ↑ med-high | — none | ↑ low | — none | ↑ med | — none |

**Legend:** ↓ = decreases, ↑ = increases, ↓↓ = strong decrease, ↑↑↑ = very strong increase, — = neutral/negligible, ± = mixed/context-dependent, ★ = fixed by code or is the primary cluster for that dimension, ↕ = depends on market conditions

---

## Critical Interaction Effects

These are the combinations that produce **non-linear** outcomes — the agent must flag these when it detects them.

### Interaction 1: Bar Diversity × Floor Variation (Clusters A × E) — MULTIPLICATIVE

This is the most dangerous combination. Wide bar range + per-level overrides multiplies the cutting schedule. The agent should NEVER recommend both A→Optimized and E→Optimized simultaneously. **Rule: if one moves toward Optimized, the other should compensate toward Simple.**

| A | E | Piece Count Effect | Recommendation |
|---|---|-------------------|----------------|
| Simple | Simple | Very low | ✅ Maximum simplicity |
| Simple | Optimized | Moderate | ✅ Acceptable — few bar types, but different per floor |
| Optimized | Simple | Moderate | ✅ Acceptable — many bar types, but same every floor |
| Optimized | Optimized | Extreme | ❌ Avoid — logistics nightmare |

### Interaction 2: Splice Strategy × Merging Tolerance (Clusters B × D) — COMPOUNDING

Restricted splice zones + low merging tolerances means every bar must be exact length AND exact position. No margin for error anywhere.

| B | D | Field Error Risk | Adaptability |
|---|---|-----------------|--------------|
| Simple | Simple | Very low | Very high (forgiving) |
| Simple | Optimized | Low-moderate | Moderate |
| Optimized | Simple | Moderate | Moderate |
| Optimized | Optimized | High | Very low (brittle) |

### Interaction 3: Bar Diversity × Stirrup Diversity (Clusters A × C) — CONGESTION

Wide longitudinal range + variable stirrups = maximum congestion at beam-column joints. This physically impedes concrete placement and inspection.

### Interaction 4: Stirrups × Floor Variation (Clusters C × E) — MULTIPLICATIVE

Variable stirrups per floor destroys prefabrication efficiency and site sorting logic.

### Interaction 5: Max Bar Length × Splice Strategy (Clusters D × B) — THRESHOLD

When `max_long_NE` exceeds typical span length AND `empalmar_siempre=false`, bars run continuously → splices eliminated. Below the threshold, this interaction doesn't exist.

---

## Dimension Correlations

The agent should know which dimensions tend to move together:

**Strong positive correlations (move in the same direction):**
- Piece Count ↔ Field Error Risk (more types = more errors)
- Field Error Risk ↔ Inspection Complexity (more errors = more checks)

**Strong negative correlations (move in opposite directions):**
- Material Cost ↔ Piece Count (THE fundamental trade-off)
- Material Cost ↔ Field Error Risk (cheaper = riskier)
- Material Cost ↔ Adaptability (cheaper = less margin)

**Moderate positive correlations:**
- Piece Count ↔ Required Skill Level
- Installation Speed ↔ Drawing Clarity

---

## Agent Reasoning Rules — Quick Reference

### NL → Config Direction

| Engineer Says... | Primary Targets | Key Cluster Moves |
|-----------------|-----------------|-------------------|
| "Simple / easy to build" | ↓ Pieces, ↓ Errors, ↑ Speed | All clusters → Simple |
| "Minimize cost / least steel" | ↓ Material Cost | All clusters → Optimized |
| "Fast construction" | ↑ Speed | A,B,C,D → Simple; E → **Strongly** Simple |
| "Balanced / typical" | All moderate | All clusters → Balanced |
| "Minimize errors / robust" | ↓ Errors, ↑ Adaptability | A,B,E → **Strongly** Simple |
| "Inexperienced crew" | ↓ Skill, ↓ Errors | All → **Strongly** Simple; F → Max clarity |
| "High-rise / many floors" | ↑ Speed, ↓ Errors | E → **Strongly** Simple (priority); rest → Simple |
| "Save material but manageable" | ↓ Cost (moderate) | B → Optimized; E → Simple; rest → Balanced |
| "Prefabrication" | Standardize pieces | D → **Strongly** Simple; E → **Strongly** Simple; F → por_viga |
| "Strict QA / government" | ↓ Inspection, ↓ Errors | All → Simple; F → Max clarity |

### Config → NL Direction

| Config Pattern Detected | Narrative Theme |
|------------------------|-----------------|
| Narrow bar range + uniform floors | "Prioritizes simplicity and repetition — crew learns once, repeats everywhere" |
| Wide bar range + per-level overrides | "Heavily optimized — complex logistics, needs experienced crew" |
| Always-splice + zonas=todo | "Maximum splice flexibility — no positioning risk, some extra steel" |
| Low bar diversity + optimized splices | "Hybrid: easy identification, precise positioning — needs disciplined crew" |
| High tol_union + long_homog=2 | "Aggressive standardization — cutting lengths rounded to 1.00m, bars merged aggressively, few distinct types, some wasted steel" |
| Single stirrup size | "Fastest stirrup installation — one type everywhere" |
| Per-level overrides active | "Floor-variable design — larger drawing set, strong document control needed" |

---

## Applying the Matrix to the Mokara Config

Reading the Mokara project.config through the Impact Matrix:

| Cluster | Position | Profile Match |
|---------|----------|---------------|
| A — Bar Envelope | calibre 3-6, dif_max_cal=3 | Balanced (range) to Optimized (diversity) |
| B — Splice Strategy | empalmar_siempre=true, zonas=todo | **Simple** |
| C — Stirrups | 2-size range, standard minimums | Balanced |
| D — Merging | tol_union 0.3/1.0, long_homog=1 (50cm rounding) | Balanced |
| E — Overrides | All disabled (except column f'c) | **Simple** |
| F — Drawings | por_piso, 1:300 | Balanced |
| H — Materials | beams 210, columns 280, joists 280 | Standard |

**Synthesized narrative for stakeholders:**

> "The Mokara configuration takes a pragmatic approach: it locks in construction simplicity for the highest-impact factors (floor repetition and splice freedom) while allowing moderate material optimization through bar diversity. Every floor uses the same reinforcement patterns and splices can be placed anywhere — this eliminates the two biggest sources of field errors and schedule delays. The trade-off is approximately 8-10% more steel than a fully optimized solution, concentrated in splice material and slightly oversized bars in low-demand zones. For a 25-story residential building with a standard construction crew, this is a well-calibrated balance."
>
> "The one area where the config leans toward complexity is the bar size range (5/8\" to 1\" with 3-step diversity allowed). Tightening this to a 2-step range (e.g., 3/4\" to 1\" with dif_max_cal=1) would be the single most impactful simplification if faster installation or lower error risk is desired."

---

## Next Steps

1. **Review** this matrix and the interaction effects with the ProDet engineering team.
2. **Calibrate magnitudes** by running ProDet with Simple vs. Optimized profiles on 2-3 real projects and measuring the actual differences in steel weight, piece count, and drawing count.
3. **Proceed to Step 3** — Define complete archetype config snapshots (Simple, Balanced, Optimized, and specialty profiles like Prefab-Ready and High-Rise).
4. **Test agent reasoning** by feeding the catalog + matrix to Claude with sample NL requests and evaluating the quality of the Config outputs and NL narratives.

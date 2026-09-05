# ProDet Archetype Profiles — Companion Guide

**Version:** 1.0.0 | **Date:** 2026-02-27 | **Step 3 of NL↔Config Agent System**

## Purpose

Archetypes are **complete config snapshots** that the agent uses as starting points. Instead of building a config from scratch (which requires setting 50+ parameters), the agent selects the closest archetype and adjusts only the parameters that the engineer's specific request warrants.

---

## The Six Archetypes at a Glance

| # | Name | Tagline | Steel Premium | Speed Gain | Error Risk |
|---|------|---------|---------------|------------|------------|
| 1 | **Simple/Robust** | Build it once, build it right | +12-20% | +25-40% faster | Very Low |
| 2 | **Balanced** | Standard practice | baseline | baseline | Moderate |
| 3 | **Cost-Optimized** | Every bar earns its keep | -8-15% | -25-40% slower | High |
| 4 | **High-Rise Repetitive** | Learn the floor once, build it 25× | +3-8% | +30-50% faster | Low |
| 5 | **Speed-Focused** | The crane doesn't wait | +15-25% | +40-60% faster | Very Low |
| 6 | **Prefab-Ready** | The cage arrives complete | +12-20% | +50-70% faster* | Very Low |

*\*Speed gain is on-site time only; factory time is additional but parallelized.*

---

## Key Parameter Comparison

### Cluster A — Bar Envelope

| Parameter | Simple | Balanced | Cost-Opt | High-Rise | Speed | Prefab |
|-----------|--------|----------|----------|-----------|-------|--------|
| `calibre_min` (beams) | **4** (3/4") | 3 (5/8") | 2 (1/2") | 3 (5/8") | **4** (3/4") | **4** (3/4") |
| `calibre_max` (beams) | **5** (7/8") | 6 (1") | 7 (1-1/4") | 5 (7/8") | **5** (7/8") | **5** (7/8") |
| `dif_max_cal` | **1** | 2 | 3 | 2 | **1** | **1** |
| `dif_cal_unir_ppal` | **2** | 1 | 0 | 1 | **2** | **2** |
| Effective # beam bar types | **~2** | ~4 | ~6+ | ~3 | **~2** | **~2** |

**Pattern:** Simple, Speed, and Prefab cluster together with the narrowest bar range. Cost-Optimized is the widest. High-Rise is a moderate compromise.

### Cluster B — Splice Strategy

| Parameter | Simple | Balanced | Cost-Opt | High-Rise | Speed | Prefab |
|-----------|--------|----------|----------|-----------|-------|--------|
| `empalmar_siempre` | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| `zonas_empalme` (I) | todo | todo | **centro** | todo | todo | todo |
| `zonas_empalme` (S) | todo | todo | **centro** | todo | todo | todo |

**Pattern:** Only Cost-Optimized restricts splices. All others allow splicing anywhere — the Colombian industry default.

### Cluster C — Stirrups

| Parameter | Simple | Balanced | Cost-Opt | High-Rise | Speed | Prefab |
|-----------|--------|----------|----------|-----------|-------|--------|
| Beam ext stirrup | **3/8" only** | 3/8"-1/2" | 3/8"-1/2" | 3/8"-1/2" | **3/8" only** | **3/8" only** |
| Beam int stirrup | **3/8" only** | 3/8"-1/2" | 3/8"-1/2" | **3/8" only** | **3/8" only** | **3/8" only** |

**Pattern:** Simple, Speed, and Prefab force a single stirrup size. High-Rise allows a narrow range for external stirrups only. Cost-Optimized uses the full 3/8"-1/2" range for both interior and exterior.

### Cluster D — Merging & Tolerances

| Parameter | Simple | Balanced | Cost-Opt | High-Rise | Speed | Prefab |
|-----------|--------|----------|----------|-----------|-------|--------|
| `long_homog` | 2 (1.00m) | 1 (0.50m) | **0** (0.10m) | 1 (0.50m) | **2** (1.00m) | **2** (1.00m) |
| `max_long_NE` | 12.0 | 9.0 | **12.0** | 10.5 | 9.0 | 9.0 |
| `maxva` | 6 | 12 | **12** | 10 | **4** | **4** |

**Pattern:** `long_homog` is the primary merging control. Clear gradient from Prefab/Speed (coarsest rounding, long_homog=2, 1.00m multiples — maximum bar standardization) through to Cost-Optimized (finest rounding, long_homog=0, 0.10m multiples — minimum merging). Note: `tol_union` still exists in config files but no longer produces changes in reinforcement; effective merging is determined by the `long_homog` normalization multiple. `maxva` is capped at 12 in the Colombian context.

### Cluster F — Drawings

| Parameter | Simple | Balanced | Cost-Opt | High-Rise | Speed | Prefab |
|-----------|--------|----------|----------|-----------|-------|--------|
| Organization | por_piso | por_piso | por_piso | por_piso | por_piso | **inline** |

**Pattern:** Only Prefab changes the drawing organization to inline (elements from consecutive stories combined in same sheet, matching factory workflow). All others use por_piso — the Colombian standard for floor-by-floor construction.

---

## Archetype Selection Decision Tree

```
Engineer's Request
│
├── Mentions SPEED / SCHEDULE / DEADLINE?
│   ├── Yes → Is it a tall building (15+ floors)?
│   │   ├── Yes → HIGH-RISE REPETITIVE
│   │   └── No → SPEED-FOCUSED
│   └── No ↓
│
├── Mentions COST / MATERIAL / MINIMIZE STEEL?
│   ├── Yes → Is the crew experienced (5+ years)?
│   │   ├── Yes → COST-OPTIMIZED
│   │   └── No → BALANCED (with Cluster B toward Optimized)
│   └── No ↓
│
├── Mentions SIMPLE / ERRORS / INEXPERIENCED / ROBUST?
│   ├── Yes → SIMPLE/ROBUST
│   └── No ↓
│
├── Mentions PREFAB / CAGE / FACTORY?
│   ├── Yes → PREFAB-READY
│   └── No ↓
│
├── Mentions TALL BUILDING / HIGH-RISE / TOWER?
│   ├── Yes → HIGH-RISE REPETITIVE
│   └── No ↓
│
└── No clear signal → BALANCED
```

---

## How the Agent Uses Archetypes

### NL → Config Workflow

1. **Parse** the NL request and identify the primary construction priority.
2. **Select** the closest archetype using the decision tree.
3. **Check** for secondary signals that warrant cluster-level adjustments.
4. **Generate** the config by starting from the archetype and modifying specific parameters.
5. **Validate** that no dangerous interactions are active (especially B×D, A×C).
6. **Disclose** the expected trade-offs using the archetype's `expected_outcomes`.

### Config → NL Workflow

1. **Read** the input config's parameter values.
2. **Score** each cluster against the 6 archetypes to find the closest match per cluster.
3. **Identify** the overall best-matching archetype and any cluster-level deviations.
4. **Generate** a narrative using the matching archetype's description as the base, noting where the config deviates.
5. **Flag** any active interactions (especially B×D, A×C).
6. **Tailor** the narrative to the target audience (owner, contractor, foreman, inspector).

### Example: Mokara Config → Archetype Matching

| Cluster | Closest Archetype | Distance |
|---------|-------------------|----------|
| A | Balanced (calibre 3-6, dif=3) | Low |
| B | Simple (empalmar=true, todo) | Zero |
| C | Balanced (2-size range) | Low |
| D | Balanced (long_homog=1, 0.50m rounding) | Zero |
| F | Balanced (por_piso) | Zero |

**Overall:** Mokara is closest to **Balanced** with **Cluster B pulled toward Simple**. This is a sensible hybrid: moderate material optimization with maximum construction flexibility and floor repetition.

---

## Next Steps

1. **Review** these archetypes with the ProDet team — are the parameter values reasonable for each profile?
2. **Calibrate** by running ProDet with at least the Simple and Cost-Optimized archetypes on a real project and comparing outputs (kg, piece count, drawing count).
3. **Proceed to Step 4** — Design the agent system prompts using the catalog (Step 1), matrix (Step 2), and archetypes (Step 3) as context.
4. **Test** the complete NL↔Config flow end-to-end.

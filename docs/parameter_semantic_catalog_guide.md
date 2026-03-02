# ProDet Parameter Semantic Catalog — Companion Guide

**Version:** 1.0.0 | **Date:** 2026-02-27 | **Project Reference:** DMO_MOK (Ejemplo Mokara)

## Purpose

This document is the human-readable companion to `parameter_semantic_catalog.json`. Together they form **Step 1** of the NL↔Config bidirectional agent system. The JSON is designed to be loaded directly into agent context; this guide is designed for engineers to review, validate, and iterate on the parameter mappings.

---

## Cluster Summary

| Cluster | Name | # Params | Key Trade-off |
|---------|------|----------|---------------|
| **A** | Bar Complexity Envelope | 11 | Simplicity vs. Material Efficiency |
| **B** | Splice & Development Strategy | 8 | Field Flexibility vs. Steel Savings |
| **C** | Stirrup Configuration | 7+ | Labor Intensity vs. Shear Optimization |
| **D** | Geometric Tolerances & Merging | 11 | Piece Diversity vs. Material Waste |
| **E** | Per-Level & Per-Section Overrides | 5 | Repetition vs. Zone Optimization |
| **F** | Drawing & Presentation | 6 | Readability vs. Sheet Count |
| **G** | Code & Design Basis | 9 | Fixed by code (not tunable) |
| **H** | Material Specification | 4 | Concrete Cost vs. Steel Savings |

---

## Cluster A: Bar Complexity Envelope

**What it controls:** The range and diversity of longitudinal bar diameters.

**The fundamental trade-off:** A narrow bar envelope (e.g., only 3/4" and 7/8") produces solutions where every beam looks similar — easy to build, easy to check, minimal sorting on site. A wide envelope (e.g., 1/2" through 1-1/4") lets the optimizer pick the perfect bar for each demand point, minimizing total steel weight but creating a complex mix of bar types that the crew must carefully manage.

### Key Parameters

| Parameter | Simple | Balanced | Optimized | Config Value |
|-----------|--------|----------|-----------|-------------|
| `calibre_min` (beams) | 4 (3/4") | 3 (5/8") | 2 (1/2") | 3 |
| `calibre_max` (beams) | 5 (7/8") | 6 (1") | 7 (1-1/4") | 6 |
| `dif_max_cal` (beams) | 1 | 2 | 3 | 3 |
| `dif_cal_unir_ppal` | 2 | 1 | 0 | 1 |
| `dif_cal_unir_adic` | 2 | 1 | 0 | 1 |

### How the Current Config Reads

The Mokara config uses `calibre_min=3` (5/8") through `calibre_max=6` (1"), with `dif_max_cal=3` allowing significant diversity. This is a **balanced-to-optimized** bar envelope — the engine has freedom to mix bar sizes across a 4-step range. For a simpler solution, narrowing to `calibre_min=4, calibre_max=5, dif_max_cal=1` would dramatically reduce bar diversity.

---

## Cluster B: Splice & Development Strategy

**What it controls:** Where and how bars connect — lap splices, hooks, development lengths, splice zone restrictions.

**The fundamental trade-off:** Permissive splicing (splice anywhere, always splice at supports) standardizes the bar schedule and simplifies field coordination. Restricted splicing (only at midspan, only in low-stress zones) reduces splice steel by 10-20% but requires the crew to position bars exactly in the allowed zones — a significant field coordination burden.

### Key Parameters

| Parameter | Simple | Balanced | Optimized | Config Value |
|-----------|--------|----------|-----------|-------------|
| `empalmar_siempre` | true | true | false | true |
| `zonas_empalme` (I/S) | todo/todo | centro/apoyo | centro/centro | todo/todo |
| `forzar_traslapo_GG` | false | false | true | false |
| `factor_tras_cra` | 1.3 | 1.3 | 1.0* | 1.3 |
| `cabezas_ganchos` | true | true | true | true |

*\*1.0 only if code allows — typically not for DMO/DES*

### How the Current Config Reads

The Mokara config uses `empalmar_siempre=true` with `zonas_empalme="todo"` for both faces. This is the **simplest** splice strategy — bars are always spliced (no continuous bars across spans) and splices can go anywhere. This maximizes construction flexibility at the cost of ~10-15% extra splice steel. For a 25-story building this trade-off makes sense: the crew does the same thing on every floor.

---

## Cluster C: Stirrup Configuration

**What it controls:** Transverse reinforcement — stirrup bar sizes, spacing, confinement zones.

**The fundamental trade-off:** Stirrups are the most labor-intensive rebar component. A simple stirrup schedule (one stirrup type, uniform spacing) dramatically speeds up fabrication and placement. A variable schedule (different spacings in different zones, multiple stirrup types) optimizes shear reinforcement but multiplies the fabrication effort.

### Key Parameters

| Parameter | Simple | Balanced | Optimized | Config Value |
|-----------|--------|----------|-----------|-------------|
| `n_estribos_min` (beams) | 5 | 5 | 3 | 5 |
| `ramas_minimas_globales` (beams) | 2 | 2 | 2 | 2 |
| `calibre_est_ext` range | 1-1 | 1-2 | 0-2 | 1-2 |
| `calibre_est_int` range | 1-1 | 1-2 | 0-2 | 1-2 |
| `sep_min` | 10 | 10 | 7.5 | 10 |
| `sep_apoyo` | 5 | 5 | 5 | 5 |

### How the Current Config Reads

Standard stirrup configuration. The 3/8"-to-1/2" range for both internal and external stirrups means two possible stirrup sizes. For a **simple** profile, forcing both min and max to the same value (e.g., calibre_est_*_min = calibre_est_*_max = 1) would create a "one stirrup size fits all" approach — fastest possible fabrication.

---

## Cluster D: Geometric Tolerances & Bar Merging

**What it controls:** How aggressively the engine groups bars into common lengths and configurations.

**The fundamental trade-off:** Higher tolerances merge more bars into standard lengths — fewer entries on the cutting schedule, fewer types in the warehouse, fewer decisions on site. But every merger means some bars are longer than strictly needed = more steel.

### Key Parameters

| Parameter | Simple | Balanced | Optimized | Config Value |
|-----------|--------|----------|-----------|-------------|
| `tol_union` (S/I) | 0.5/1.5 | 0.3/1.0 | 0.1/0.3 | 0.3/1.0 |
| `long_homog` | 2 (1.00m) | 1 (0.50m) | 0 (0.10m) | 1 |
| `max_long_NE` | 9.0 | 10.5 | 12.0 | 10.5 |
| `maxva` | 6 | 12 | 24 | 12 |
| `text_capas` | 3 | 3 | 4 | 3 |
| `ganch_medios` | false | false | true | false |

### How the Current Config Reads

The Mokara config is squarely **balanced**. The `tol_union` of 0.3m (top) / 1.0m (bottom) provides moderate merging — bottom bars are merged more aggressively (1.0m tolerance) because bottom bar lengths vary less between spans. `long_homog=1` rounds cutting lengths to 50cm multiples — the standard Colombian practice (bars come out as 1.50m, 2.00m, 2.50m, etc.). `max_long_NE=10.5m` matches the standard Colombian commercial bar length.

---

## Cluster E: Per-Level & Per-Section Overrides

**What it controls:** Whether parameters vary by floor and/or cross-section geometry.

**The fundamental trade-off:** This is the "repetition multiplier." Every active override means different drawings, different bar schedules, different stirrup patterns on different floors. In a 25-story building, disabling all overrides means the crew learns one pattern and repeats it 25 times. Enabling them means potentially 25 different patterns to learn.

### Key Parameters

| Parameter | Simple | Balanced | Optimized | Config Value |
|-----------|--------|----------|-----------|-------------|
| `forzar_ref_ppal.filtro_por_nivel` (beams) | false | false | true | false |
| `est_min.filtro_por_nivel` (beams) | 0 | 0 | 1 | 0 |
| `fc.filtro_por_nivel` (beams) | 0 | 0 | 1 | 0 |
| `fc.filtro_por_nivel` (columns) | false | true | true | true |

### How the Current Config Reads

Almost all overrides are **disabled** for beams and joists — same rules every floor. The one exception is column concrete strength, where `filtro_por_nivel=true` is active (though currently all floors are set to 280 kg/cm²). This config strongly favors **construction repetition** at the expense of per-floor optimization.

---

## Cluster F: Drawing & Presentation

**What it controls:** How shop drawings are organized, scaled, and annotated.

### Key Parameters

| Parameter | Simple | Balanced | Optimized | Config Value |
|-----------|--------|----------|-----------|-------------|
| `tipo_diagramacion` | por_piso | por_piso | por_viga | por_piso |
| `escala_esquema` | 200 | 300 | 400 | 300 |
| `escala_seccion` | 200 | 300 | 300 | 300 |
| `apoyos_con_hatch` | C | C | C | C |

### How the Current Config Reads

Standard drawing configuration — by floor, 1:300 scale, concrete hatching at supports. This is the most common setup for Colombian high-rise construction.

---

## Clusters G & H: Code Basis & Materials

These clusters are largely **non-negotiable** — they're set by the structural design code (NSR-10), the project's seismic classification, and the structural engineer's design decisions. The agent must understand them to explain constraints but should not suggest changing them for constructability reasons.

**Key observations from the Mokara config:**
- **Seismic demand:** DMO (Moderate) — intermediate confinement requirements.
- **Beam f'c:** 210 kg/cm² (standard, all floors).
- **Column f'c:** 280 kg/cm² (standard, all floors — higher than beams as expected).
- **Joist f'c:** 280 kg/cm².
- **Steel fy:** 4200 kg/cm² (Grade 60) everywhere.
- **Covers:** 4cm (beams), 4cm (columns), 2cm (joists) — standard for normal exposure.

---

## Floor Grouping (grupos_niveles) — Project-Level Strategy

**What it controls:** Which floors are grouped together to receive identical reinforcement computed from the envelope of forces across the group.

**The fundamental trade-off:** Floor grouping trades material efficiency (envelope produces heavier reinforcement than per-floor optimization) for construction speed (crew repetition, learning curve, fewer drawing sets, simpler logistics). This is a project-level decision, not a per-parameter tuning.

### Trade-off Table

| Strategy | Steel Impact | Piece Count | Speed Impact | Best For |
|----------|-------------|-------------|-------------|----------|
| No grouping | Baseline | Baseline | Baseline | Low-rise, unique floors |
| Moderate (pairs) | +2-4% | -15-25% | +15-25% | Mid-rise with some identical floors |
| Aggressive (4+ per group) | +5-8% | -30-50% | +30-50% | High-rise towers with many typical floors |

### Cluster Interactions

- **Synergistic with Cluster E** (per-level overrides disabled): Grouping + no overrides = maximum repetition. This is the ideal combination for High-Rise Repetitive (Arch-04).
- **Compounds with Archetype 4**: Floor grouping is the natural complement to the High-Rise Repetitive archetype.
- **Contradicts aggressive Cluster A**: Wide bar range + grouping means the envelope picks the heaviest bar from ANY floor in the group — diminishing returns on material optimization.
- **Neutral with Clusters B, C, D, F**: Floor grouping doesn't directly interact with splice strategy, stirrup config, merging tolerances, or drawing format.

### Constraints

- Only consecutive floors can be grouped
- Only geometrically identical floors (same column layout, beam spans, slab geometry)
- Mode is always "envolvente" (envelope of forces)
- Transfer floors, mezzanines, roof/machine room, and podium levels should NOT be grouped with typical floors

---

## Overall Config Profile Assessment

The Mokara project.config falls in the **balanced-to-simple** range:

| Dimension | Assessment | Evidence |
|-----------|------------|----------|
| Bar diversity | Balanced | calibre 3-6, dif_max_cal=3 |
| Splice strategy | Simple | empalmar_siempre=true, zonas=todo |
| Stirrup complexity | Balanced | 2-size range, standard minimums |
| Bar merging | Balanced | tol_union moderate, long_homog=1 (50cm rounding) |
| Floor repetition | Simple | All per-level overrides disabled |
| Drawing setup | Balanced | Standard scales and organization |

**For the construction crew:** This config produces a building where every floor is essentially the same (high repetition), splicing is unrestricted (flexible placement), and bar diversity is moderate. The main complexity driver is the 4-step bar size range within beams — tightening this to 2 steps would be the single highest-impact simplification.

---

## Next Steps

1. **Validate** this catalog with the ProDet engine team to confirm parameter ranges and interactions.
2. **Build the Impact Matrix** (Step 2) using these clusters and the construction dimensions defined in the JSON metadata.
3. **Define archetype profiles** (Step 3) as complete config snapshots using the Simple/Balanced/Optimized values from this catalog.
4. **Test** the Config→NL direction by feeding the catalog + a config to Claude and evaluating the narrative output.
5. **Test** the NL→Config direction by giving natural language requirements and checking whether the agent produces reasonable parameter values.

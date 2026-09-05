# ProDet Parameter Semantic Catalog — Companion Guide

**Version:** 1.0.0 | **Date:** 2026-02-27 | **Project Reference:** DMO\_MOK (Ejemplo Mokara)

## Purpose

This document is the human-readable companion to `parameter\_semantic\_catalog.json`. Together they form **Step 1** of the NL↔Config bidirectional agent system. The JSON is designed to be loaded directly into agent context; this guide is designed for engineers to review, validate, and iterate on the parameter mappings.

\---

## Cluster Summary

|Cluster|Name|# Params|Key Trade-off|
|-|-|-|-|
|**A**|Bar Complexity Envelope|11|Simplicity vs. Material Efficiency|
|**B**|Splice \& Development Strategy|8|Field Flexibility vs. Steel Savings|
|**C**|Stirrup Configuration|7+|Labor Intensity vs. Shear Optimization|
|**D**|Geometric Tolerances \& Merging|11|Piece Diversity vs. Material Waste|
|**F**|Drawing \& Presentation|6|Readability vs. Sheet Count|
|**G**|Code \& Design Basis|9|Fixed by code (not tunable)|
|**H**|Material Specification|4|Concrete Cost vs. Steel Savings|

\---

## Cluster A: Bar Complexity Envelope

**What it controls:** The range and diversity of longitudinal bar diameters.

**The fundamental trade-off:** A narrow bar envelope (e.g., only 3/4" and 7/8") produces solutions where every beam looks similar — easy to build, easy to check, minimal sorting on site. A wide envelope (e.g., 1/2" through 1-1/4") lets the optimizer pick the perfect bar for each demand point, minimizing total steel weight but creating a complex mix of bar types that the crew must carefully manage.

### Key Parameters

|Parameter|Simple|Balanced|Optimized|Config Value|
|-|-|-|-|-|
|`calibre\_min` (beams)|4 (3/4")|3 (5/8")|2 (1/2")|3|
|`calibre\_max` (beams)|5 (7/8")|6 (1")|7 (1-1/4")|6|
|`dif\_max\_cal` (beams)|1|2|3|3|
|`dif\_cal\_unir\_ppal`|2|1|0|1|
|`dif\_cal\_unir\_adic`|2|1|0|1|

### How the Current Config Reads

The Mokara config uses `calibre\_min=3` (5/8") through `calibre\_max=6` (1"), with `dif\_max\_cal=3` allowing significant diversity. This is a **balanced-to-optimized** bar envelope — the engine has freedom to mix bar sizes across a 4-step range. For a simpler solution, narrowing to `calibre\_min=4, calibre\_max=5, dif\_max\_cal=1` would dramatically reduce bar diversity.

\---

## Cluster B: Splice \& Development Strategy

**What it controls:** Where and how bars connect — lap splices, hooks, development lengths, splice zone restrictions.

**The fundamental trade-off:** Permissive splicing (splice anywhere, always splice at supports) standardizes the bar schedule and simplifies field coordination. Restricted splicing (only at midspan, only in low-stress zones) reduces splice steel by 10-20% but requires the crew to position bars exactly in the allowed zones — a significant field coordination burden.

### Key Parameters

|Parameter|Simple|Balanced|Optimized|Config Value|
|-|-|-|-|-|
|`empalmar\_siempre`|true|true|false|true|
|`zonas\_empalme` (I/S)|todo/todo|centro/apoyo|centro/centro|todo/todo|
|`forzar\_traslapo\_GG`|false|false|true|false|
|`factor\_tras\_cra`|1.3|1.3|1.0\*|1.3|
|`cabezas\_ganchos`|true|true|true|true|



\############################################################################################

The available splice zone options are: **"todo"**, **"centro"**, and **"sesgado"**.

* **"todo"**: Splices can be placed anywhere along the span.
* **"centro"**: Splices are located at the midspan.
* **"sesgado"**: Splices are located in the first third or the last third of each span.

\############################################################################################

*\*1.0 only if code allows — typically not for DMO/DES*

### How the Current Config Reads

The Mokara config uses `empalmar\_siempre=true` with `zonas\_empalme="todo"` for both faces. This is the **simplest** splice strategy — bars are always spliced (no continuous bars across spans) and splices can go anywhere. This maximizes construction flexibility at the cost of \~10-15% extra splice steel. For a 25-story building this trade-off makes sense: the crew does the same thing on every floor.

\---

## Cluster C: Stirrup Configuration

**What it controls:** Transverse reinforcement — stirrup bar sizes, spacing, confinement zones.

**The fundamental trade-off:** Stirrups are the most labor-intensive rebar component. A simple stirrup schedule (one stirrup type, uniform spacing) dramatically speeds up fabrication and placement. A variable schedule (different spacings in different zones, multiple stirrup types) optimizes shear reinforcement but multiplies the fabrication effort.

\############################################################################################



### Key Parameters

|Parameter|Simple|Balanced|Optimized|Config Value|
|-|-|-|-|-|
|`calibre\_est\_ext` range|1-1|1-2|1-2|1-2|
|`calibre\_est\_int` range|1-1|1-2|1-2|1-2|

\############################################################################################



### How the Current Config Reads

Standard stirrup configuration. The 3/8"-to-1/2" range for both internal and external stirrups means two possible stirrup sizes. For a **simple** profile, forcing both min and max to the same value (e.g., calibre\_est\_*min = calibre\_est*\_max = 1) would create a "one stirrup size fits all" approach — fastest possible fabrication.

\---

## Cluster D: Geometric Tolerances \& Bar Merging

**What it controls:** How aggressively the engine groups bars into common lengths and configurations.

**The fundamental trade-off:** Higher tolerances merge more bars into standard lengths — fewer entries on the cutting schedule, fewer types in the warehouse, fewer decisions on site. But every merger means some bars are longer than strictly needed = more steel.

### Key Parameters

|Parameter|Simple|Balanced|Optimized|Config Value|
|-|-|-|-|-|
|`tol\_union` (S/I)|0.5/1.5|0.3/1.0|0.1/0.3|0.3/1.0|
|`long\_homog`|2|1|0|1|
|`max\_long\_NE`|12.0|9.0|10.5|10.5|
|`maxva`|6|12|24|12|

\############################################################################################

The parameter **`tol\_union`** defined in the configuration no longer produces changes in the reinforcement.

This parameter now depends on the **length multiples used to normalize the bars**. Thus, bar merging is controlled by the normalization multiple.

For example:

* If bars are normalized to **50 cm multiples**, bars whose **end points are within about 50 cm** will tend to be merged.
* If bars are normalized to **10 cm multiples**, only bars whose **end points are very close (within about 10 cm)** will be merged.
* If bars are normalized to **100 cm multiples**, bars whose **end points are within about 100 cm** may be merged.

Therefore, the effective merging tolerance is now determined by the **normalization multiple**, rather than directly by `tol\_union`.



For the Colombian context, the parameter **`maxva`** must not exceed **12 m**.

The parameter **`long\_homog`** has three options:

* **0**: Bars are normalized to **10 cm multiples**.
* **1**: Bars are normalized to **50 cm multiples**.
* **2**: Bars are normalized to **100 cm multiples**.

\############################################################################################



### How the Current Config Reads

The Mokara config is squarely **balanced**. The `tol\_union` of 0.3m (top) / 1.0m (bottom) provides moderate merging — bottom bars are merged more aggressively (1.0m tolerance) because bottom bar lengths vary less between spans. `max\_long\_NE=10.5m` matches the standard Colombian commercial bar length.

## Cluster F: Drawing \& Presentation

**What it controls:** How shop drawings are organized, scaled, and annotated.

### Key Parameters

|Parameter|Simple|Balanced|Optimized|Config Value|
|-|-|-|-|-|
|`tipo\_diagramacion`|por\_piso|por\_piso|por\_viga|por\_piso|
|`apoyos\_con\_hatch`|C|C,V|C|C|

\############################################################################################

There are two options for the parameter **`tipo\_diagramacion`**:

* **"por\_piso"**: Elements from different stories will **not be combined**. Each drawing sheet will only contain elements from a single story.
* **"inline"**: Empty spaces in the drawings will be **filled with elements from consecutive stories**, allowing elements from different levels to be combined in the same sheet.

\############################################################################################

### How the Current Config Reads

Standard drawing configuration — by floor, 1:300 scale, concrete hatching at supports. This is the most common setup for Colombian high-rise construction.

\---

## Clusters G \& H: Code Basis \& Materials

These clusters are largely **non-negotiable** — they're set by the structural design code (NSR-10), the project's seismic classification, and the structural engineer's design decisions. The agent must understand them to explain constraints but should not suggest changing them for constructability reasons.

**Key observations from the Mokara config:**

* **Seismic demand:** DMO (Moderate) — intermediate confinement requirements.
* **Beam f'c:** 210 kg/cm² (standard, all floors).
* **Column f'c:** 280 kg/cm² (standard, all floors — higher than beams as expected).
* **Joist f'c:** 280 kg/cm².
* **Steel fy:** 4200 kg/cm² (Grade 60) everywhere.
* **Covers:** 4cm (beams), 4cm (columns), 2cm (joists) — standard for normal exposure.

\---

## Floor Grouping (grupos\_niveles) — Project-Level Strategy

**What it controls:** Which floors are grouped together to receive identical reinforcement computed from the envelope of forces across the group.

**The fundamental trade-off:** Floor grouping trades material efficiency (envelope produces heavier reinforcement than per-floor optimization) for construction speed (crew repetition, learning curve, fewer drawing sets, simpler logistics). This is a project-level decision, not a per-parameter tuning.

### Trade-off Table

|Strategy|Steel Impact|Piece Count|Speed Impact|Best For|
|-|-|-|-|-|
|No grouping|Baseline|Baseline|Baseline|Low-rise, unique floors|
|Moderate (pairs)|+2-4%|-15-25%|+15-25%|Mid-rise with some identical floors|
|Aggressive (4+ per group)|+5-8%|-30-50%|+30-50%|High-rise towers with many typical floors|

### Cluster Interactions

* **Synergistic with uniform floor-to-floor treatment**: Grouping + no per-level overrides = maximum repetition. This is the ideal combination for High-Rise Repetitive (Arch-04).
* **Compounds with Archetype 4**: Floor grouping is the natural complement to the High-Rise Repetitive archetype.
* **Contradicts aggressive Cluster A**: Wide bar range + grouping means the envelope picks the heaviest bar from ANY floor in the group — diminishing returns on material optimization.
* **Neutral with Clusters B, C, D, F**: Floor grouping doesn't directly interact with splice strategy, stirrup config, merging tolerances, or drawing format.

### Constraints

* Only consecutive floors can be grouped
* Only geometrically identical floors (same column layout, beam spans, slab geometry)
* Mode is always "envolvente" (envelope of forces)
* Transfer floors, mezzanines, roof/machine room, and podium levels should NOT be grouped with typical floors

\---

## Overall Config Profile Assessment

The Mokara project.config falls in the **balanced-to-simple** range:

|Dimension|Assessment|Evidence|
|-|-|-|
|Bar diversity|Balanced|calibre 3-6, dif\_max\_cal=3|
|Splice strategy|Simple|empalmar\_siempre=true, zonas=todo|
|Stirrup complexity|Balanced|2-size range, standard minimums|
|Bar merging|Balanced|tol\_union moderate, long\_homog=1.0|
|Floor repetition|Simple|All per-level overrides disabled|
|Drawing setup|Balanced|Standard scales and organization|

**For the construction crew:** This config produces a building where every floor is essentially the same (high repetition), splicing is unrestricted (flexible placement), and bar diversity is moderate. The main complexity driver is the 4-step bar size range within beams — tightening this to 2 steps would be the single highest-impact simplification.

\---

## Next Steps

1. **Validate** this catalog with the ProDet engine team to confirm parameter ranges and interactions.
2. **Build the Impact Matrix** (Step 2) using these clusters and the construction dimensions defined in the JSON metadata.
3. **Define archetype profiles** (Step 3) as complete config snapshots using the Simple/Balanced/Optimized values from this catalog.
4. **Test** the Config→NL direction by feeding the catalog + a config to Claude and evaluating the narrative output.
5. **Test** the NL→Config direction by giving natural language requirements and checking whether the agent produces reasonable parameter values.


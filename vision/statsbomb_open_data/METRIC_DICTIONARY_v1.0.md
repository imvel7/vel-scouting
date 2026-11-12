# StatsBomb first-pass metric dictionary

**Scope:** event-derived metrics for the initial ingestion proof.  
**Source:** StatsBomb Open Data.  
**Status:** technical definitions only; not a validated scouting rubric.

| Metric | Calculation | Limitation |
|---|---|---|
| Pass attempts | Count of player's Pass events | Only events present in selected sample |
| Pass completion % | Pass events with no `pass.outcome` / Pass attempts × 100 | StatsBomb encodes complete passes by omitting outcome |
| Mean pass length | Mean of available `pass.length` values | Not adjusted for match context or role |
| Crosses / through balls | Count of boolean flags on Pass events | Definitions follow source annotations |
| Assists / shot assists | Count of `goal_assist` / `shot_assist` pass flags | Source-defined event labels |
| Carries | Count of Carry events | Does not establish overall ball-carrying quality |
| Shots / goals / xG | Shot count, Goal outcomes, sum of available `statsbomb_xg` | xG null when no values supplied |
| Pressures | Count of Pressure events | Does not measure pressure quality or team scheme |
| Interceptions / recoveries / clearances / blocks | Counts of respective event types | Opportunity and team context are not yet modelled |
| Tackles | Duel events with `duel.type.name = Tackle` | Not a complete defensive quality assessment |
| Dribbles | Count of Dribble events | Does not measure success until outcome handling is separately validated |

## Rules

1. Do not create per-90 values until reliable minutes played are calculated and tested.
2. Do not interpret a zero as a weakness without checking the player's opportunities and team context.
3. Do not compare players across roles or competition levels without an explicit peer-group model.
4. Do not infer visual/off-ball traits from event data alone.
5. Preserve source file hashes and the importer/metric version for reproducibility.

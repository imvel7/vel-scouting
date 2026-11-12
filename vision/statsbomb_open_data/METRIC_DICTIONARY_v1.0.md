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
| Minutes played | Sum of period-local elapsed seconds while the player is active, based on Starting XI, substitutions, Player Off/On and dismissal events | Requires complete ordered timestamps and a Half End per period; unavailable rather than guessed when state/clock evidence is incomplete |

## Rules

1. Do not create per-90 values until reliable minutes played are calculated and tested.
2. Do not interpret a zero as a weakness without checking the player's opportunities and team context.
3. Do not compare players across roles or competition levels without an explicit peer-group model.
4. Do not infer visual/off-ball traits from event data alone.
5. Preserve source file hashes and the importer/metric version for reproducibility.


## First role profile — Centre-back (CB) v0.1

The importer selects players whose observed lineup/event position labels contain
`Center Back`. The CB profile currently exposes these separate fields:

| CB profile field | Calculation | What it can say | What it cannot say |
|---|---|---|---|
| Attributed events | Count of player-attributed events | How many coded actions are assigned to the player in this sample | How active or effective the player was without minutes/possession context |
| Pass attempts | Count of Pass events | Recorded distribution volume | Whether the player chose the best pass |
| Pass completions | Pass events without `pass.outcome` | Source-coded completed passes | The difficulty or value of each pass |
| Pass completion % | Completed passes / attempts × 100 | Recorded completion proportion | Whether the player's passing was progressive or press-resistant |
| Mean pass length | Mean of available `pass.length` values | Average length of coded passes | Whether longer/shorter passing was better for the tactical role |
| Carries | Count of Carry events | Recorded ball-carrying actions | Carrying quality, pressure faced or space gained without further context |
| Pressures | Count of Pressure events | Recorded pressure actions | Pressure intensity, timing quality or team press structure |
| Interceptions | Count of Interception events | Recorded interception actions | Whether the player anticipated/positioned well across all situations |
| Ball recoveries | Count of Ball Recovery events | Recorded recoveries | Recovery opportunity or team possession context |
| Clearances | Count of Clearance events | Recorded clearances | Whether the clearance was the best decision |
| Blocks | Count of Block events | Recorded blocks | Shot/pass danger or whether the block prevented a goal |
| Tackles | Duel events with `duel.type.name = Tackle` | Recorded tackle-type duels | Complete ground/aerial duel quality |

### CB profile safeguards

- Values are raw totals or source percentages over the selected sample.
- A player must have a centre-back position label to enter `role_profiles.CB`.
- `matches_with_appearance_evidence` is based on position records or attributed
  player events. It is not a minutes-played calculation.
- Minutes are calculated from the event state machine using period-local timestamps; half-time breaks and penalty shootouts are excluded. Missing or contradictory clock/state evidence leaves minutes null.
- Per-90 normalization remains disabled until the real three-match sample has passed the new minutes validation.
- No composite CB score, defensive rating, percentile or ranking is produced.
- No aerial-duel success metric is included until event labels/outcomes are
  separately validated against the source specification and real samples.
- Counts must be interpreted with sample size, team possession, defensive
  opportunities, match state and opponent context in mind.

### Real-data smoke-test sample

A GitHub Actions smoke test used three 2022 FIFA World Cup matches involving
Argentina:
- Argentina 3–0 Croatia — 13 December 2022 — match ID `3869519`
- Argentina 3–3 France — 18 December 2022 — match ID `3869685`
- Argentina 2–1 Australia — 3 December 2022 — match ID `3869151`

The test confirmed that StatsBomb player ID `20572` (Cristian Romero) was
identified with a centre-back role label and appearance evidence across all
three sample matches, and that the CB profile contained attributed passing
events. This validates the technical path only. It is not a scouting evaluation
of Romero and not evidence of contemporary youth-player data coverage.

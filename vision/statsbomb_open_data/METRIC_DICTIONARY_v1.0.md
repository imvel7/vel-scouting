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

## Per-90 normalization and CSV export

Per-90 values are produced only after the player's on-pitch minutes pass the
match-clock and player-state validation described above.

| Export field | Calculation | Rounding |
|---|---|---|
| `per90_<count_metric>` | Selected-sample count metric ÷ verified on-pitch minutes × 90 | 2 decimal places |
| `per90_xg` | Sum of available `statsbomb_xg` values ÷ verified on-pitch minutes × 90 | 3 decimal places |

The `per90_<count_metric>` fields cover `events`, `passes_attempted`,
`passes_completed`, `crosses`, `through_balls`, `assists`,
`shot_assists`, `carries`, `shots`, `goals`, `pressures`,
`interceptions`, `ball_recoveries`, `clearances`, `blocks`,
`tackles` and `dribbles`.

The CSV contains the raw aggregate fields and separate `per90_*` columns.
`per90_pass_completion_pct` and `per90_pass_length_mean` are intentionally
not created: percentages and averages are not event counts. Per-90 values are
blank when the minutes for a relevant selected-match record are unavailable,
or when the total verified minutes are zero. The denominator is the sum of
verified on-pitch seconds for that player across the selected sample, not the
number of matches or the full match duration.

These rates describe recorded event volume per 90 minutes. They are not
percentiles, peer rankings, role-adjusted measures, player ratings or scout
verdicts.

## Player-level data quality indicator

The aggregate player record and CSV include a transparent `data_quality_status`
with supporting reason codes and boolean checks. It describes data availability
inside the selected sample; it is not a measure of player ability, scouting
confidence or sample representativeness.

| Status | Rule |
|---|---|
| `complete` | At least one appearance-evidence match, at least one attributed event, and verified positive minutes across all player match records in the selected sample |
| `partial` | Appearance evidence and attributed events exist, but minutes are incomplete or no positive verified total is available |
| `insufficient` | No appearance evidence or no attributed events are available for the player in the selected sample |

Possible reason codes are `no_appearance_evidence`, `no_attributed_events`,
`minutes_calculation_incomplete` and `no_positive_verified_minutes`.
The JSON `data_quality.checks` object also records whether per-90 values are
available. CSV exports flatten the status, reason codes and core checks into
separate columns.

A `complete` status means only that these core checks passed for this selected
sample. It does not mean that the sample is large, that every event type is
captured, or that the player has been evaluated fairly against peers.

## Player identity matching across matches

Player records are grouped only by the source's stable `player_id`, exposed as
`statsbomb:<player_id>`. Player names are display labels, not matching keys.
This prevents two different players with the same name from being automatically
merged.

The JSON `identity` object and CSV fields report:

- Whether every contributing match row carries the same source player ID.
- The name variants observed for that ID.
- An identity status of `consistent` or `review`, with reason codes when a
  source-ID mismatch or name variation is found.

Name variation does not trigger an automatic split or merge. It flags the
records for human review while preserving the source ID as the grouping key.
This check does not independently verify a real-world identity outside the
source's own identifiers.

### Possible same-name players

A separate report check groups display names after case folding and collapsing
whitespace. When one normalized name belongs to multiple StatsBomb player IDs,
the report lists the IDs and their teams under
`player_identity_review.same_name_different_ids`.

The affected player rows and CSV export include a possible-collision flag and
the other source IDs. This is a review aid only: names are not treated as proof
that two records refer to the same person, and no players are merged. The check
does not use fuzzy matching, nicknames or transliteration.

## Match-to-aggregate consistency check

Each selected-sample player total is reconciled against the player's individual
match records. The check compares:

- Number of match records and appearance-evidence match count.
- Every exported raw event-count total.
- Total available xG.
- Number of match records with valid minutes and, when all minutes are valid,
  the summed minutes played.
- The exported per-90 values against a fresh calculation from the aggregate
  counts and verified seconds.

The JSON output exposes `data_consistency.status`:

| Status | Meaning |
|---|---|
| `consistent` | All applicable comparisons match. Minute/per-90 checks are marked not applicable when minute data is incomplete. |
| `review` | At least one comparable field differs between match records and the aggregate. |

The `data_consistency.reasons` array identifies a failed comparison, for
example `metric_total_mismatch:passes_attempted` or
`minutes_total_mismatch`. Supporting boolean checks and the number of checked
match records are included. CSV exports include the status, reason codes and
record count.

A `review` result is a data-reconciliation warning, not a judgement about the
player or proof that the source match record is wrong. The underlying match
records should be inspected before using the affected aggregate.

## Cross-season player comparison foundation

The importer can optionally compare the current report with one or more
previous JSON reports from the same competition by passing
`--compare-report PATH` once for each earlier season report.

Players are matched only by the stable StatsBomb `player_id`. The comparison
lists a player only when that ID is present in at least two supplied seasons.
It places selected-match counts, appearance evidence, verified minutes and
quality/consistency statuses beside the per-90 metrics for each season.

Per-90 changes are calculated as the later season's value minus the previous
season's value, only when both seasons have valid per-90 values for that metric.
When either season lacks verified minutes, the rate and change remain
unavailable rather than being estimated. Percentages and averages are not
included in this first comparison foundation.

The comparison accepts only reports for one competition and rejects duplicate
season IDs. Each season row also preserves the source position labels seen in
that sample. Position comparison is marked `same` when both seasons have the
same non-empty set of labels (case-insensitive), `changed` when both sets exist
but differ, and `unavailable` when either season has no position labels. This
is a source-label comparison, not a validated tactical-role classification;
it does not establish whether a player's responsibilities changed within a
position label.

It does not yet adjust for competition strength, age, team context, minutes
thresholds or sample representativeness. A positive per-90 change is not
automatically evidence of player improvement, and a negative change is not
automatically evidence of decline.

## Rules

1. Produce per-90 values only from validated, positive on-pitch minutes; otherwise leave them unavailable.
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
- Minutes are calculated from the event state machine using StatsBomb minute/second match-clock fields; each period is anchored to its first clock value, so half-time breaks and extra-time intervals are excluded. Penalty shootouts are excluded. Missing or contradictory clock/state evidence leaves minutes null.
- The profile exposes per-90 counts and xG only when the selected-sample minutes are complete and positive. Percentages and averages remain unnormalized.
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

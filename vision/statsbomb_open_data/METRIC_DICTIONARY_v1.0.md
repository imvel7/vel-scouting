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
player ratings or scout verdicts. The report's separate peer-benchmark section
may calculate cautious, same-role percentiles only when its explicit cohort
requirements are met.

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
season IDs. Each season row preserves the source position labels seen in that
sample and a single `position_comparison_from_previous` result. Position
comparison is marked `same` when both seasons have the same non-empty set of
labels (case-insensitive), `changed` when both sets exist but differ, and
`unavailable` when either season has no position labels. Shared labels retain
the display form recorded in the later season. The player-level summary exposes
`position_comparison_status`, `position_change_count` and
`position_data_gaps`.

These are positions recorded in the selected lineups, not a minutes-weighted
primary role or a validated tactical-role classification. They do not establish
how long the player operated in each role or whether responsibilities changed
within a position label.

It does not yet adjust for competition strength, age, team context, minutes
thresholds or sample representativeness. A positive per-90 change is not
automatically evidence of player improvement, and a negative change is not
automatically evidence of decline.

## Same-role peer benchmarks

The report includes a separate `role_benchmarks` object. The first version
compares players only within the same role profile in the same competition and
season report. It does not combine reports, competitions, seasons or roles.

A player enters a benchmark cohort only when:
- verified minutes are complete and at least **450 minutes**;
- selected-sample data quality is `complete`;
- match-to-aggregate reconciliation is `consistent`;
- source player identity status is `consistent`; and
- verified per-90 metrics are available.

A metric percentile is emitted only when at least **10 eligible players**
have a value for that same metric. Otherwise the percentile remains null and
the status is `insufficient_sample`. The percentile uses the tie-aware
midrank method: equal values share their middle rank. Each metric has its own
eligible cohort size, so one metric can be comparable while another is not.

Each metric summary also includes a descriptive cohort distribution when
the minimum cohort size is met: minimum, 25th percentile, median, 75th
percentile and maximum. Quartiles use linear interpolation over sorted
observations. When the cohort is too small, the distribution is null rather
than presented as if it were reliable.

For each eligible player/metric with a valid peer comparison, the report also
shows the difference between the player's per-90 value and the cohort median,
and whether the value falls inside the cohort's middle 50% (between p25 and
p75). These are descriptive comparisons within the same cohort, not adjusted
performance effects or evidence of player quality. The distribution includes
the player being compared.

These percentiles describe relative per-90 event frequency, not action quality,
player ability, a player ranking or a transfer recommendation. A higher
percentile is not necessarily better: for example, a high value for goals
conceded is not a positive goalkeeper outcome. Team style, possession, player
age, role variation, opposition strength and selected-sample coverage are not
adjusted in this first version. Small datasets will correctly return
`insufficient_sample` rather than manufacture a comparison.

## Benchmark metric interpretation guidance

The `role_benchmarks.metric_guidance` object documents every metric used by
the six same-role benchmark profiles. Each entry contains a display label,
unit, what the metric counts, an interpretation note and an explicit list of
what the metric does not measure.

The `directionality` field is deliberately cautious:

- `context_dependent`: the event frequency is not intrinsically positive or
  negative. A high value can reflect role, possession, team style, opportunity
  or workload rather than better performance.
- `adverse_outcome_context_dependent`: the counted event is an adverse
  outcome, but it cannot be attributed to one player without context. The
  current example is goalkeeper goals conceded.

Examples:
- Passes completed per 90 is a count, not pass-completion percentage.
- Dribbles per 90 describes recorded dribble activity, not dribble success.
- Saves per 90 can reflect more shots faced; it is not save percentage.
- Goals conceded per 90 is an adverse team outcome, not a goalkeeper rating.
- xG per 90 combines shot volume and source-model shot probabilities; it is
  not finishing above or below expectation.

No metric is labelled simply "higher is better" or "lower is better". These
notes are guardrails for interpretation, not a calibrated evaluation model.
They do not yet adjust metrics for age, league strength, team possession,
opponent quality, tactical role, match state or opportunity.

## Player scouting-review readiness gate

The report includes `player_evaluation_readiness`, a technical gate before a
human scout reviews a player. It does not assign a player score or declare
whether a player is good.

The initial statuses are:

- `ready_for_scout_review`: complete selected-sample data quality,
  consistent match reconciliation and source identity, at least **450
  verified minutes**, at least **5 appearance-evidence matches**, and
  attributed event evidence.
- `limited`: some useful data exists, but one or more appearance, sample,
  quality, reconciliation, identity or name-collision checks needs review.
- `insufficient_data`: attributed event evidence is absent.

Each player-role record includes reason codes, checked sample values,
available per-90 metrics and whether same-role peer percentiles are available.
A player can be ready for a human video/scouting review while peer percentiles
remain unavailable because the role cohort is too small. This is deliberate:
peer comparison is supporting context, not a gate that blocks all human review.

The 450-minute and 5-appearance thresholds are initial engineering defaults,
not universal scouting standards. Age, competition strength, team style,
positional opportunity, opposition level, match state and video evidence are
not yet adjusted. A readiness status is not a quality grade, potential
assessment or transfer recommendation.

## Rules

1. Produce per-90 values only from validated, positive on-pitch minutes; otherwise leave them unavailable.
2. Do not interpret a zero as a weakness without checking the player's opportunities and team context.
3. Compare players only through an explicit same-role, same-competition and same-season peer group; do not treat percentiles as quality ratings.
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

### W profile metric groups

The importer produces an explicit winger profile under `role_profiles.W`.
It selects position labels containing the standalone token `Wing` while
excluding labels that also identify a `Back` or `Fullback`. This includes
source labels such as `Left Wing` and `Right Wing`, but not wing-backs,
centre-forwards or side-midfield labels. Original position labels remain
available on each player row.

The profile groups existing event metrics into four sections:

- **Chance creation and finishing:** shot assists, assists, shots, goals and xG.
- **Wide delivery and passing:** crosses, through balls, pass attempts and
  completions; pass completion percentage and mean pass length remain
  contextual fields.
- **One-v-one and ball progression:** dribbles and carries.
- **Pressing and defensive contribution:** pressures, tackle-type duels,
  interceptions and ball recoveries.

Raw counts are retained. Count metrics and xG receive per-90 values only when
the player record contains rates calculated from complete, positive verified
minutes. The groups do not measure successful take-on rate, crossing quality,
off-ball runs or tactical decision quality; no rating or ranking is produced.

### GK profile metric groups

The importer produces a goalkeeper profile under `role_profiles.GK`. It
selects only explicit `Goalkeeper`, `Goal Keeper` or `Keeper` position
labels; a keeper-sweeper action label is not treated as a playing position.

The profile groups existing event fields into three sections:

- **Shot stopping:** goalkeeper save events, shot-faced events, goal-conceded
  events and penalty-save/concession events.
- **Area control:** collections, punches, sweeps and smothers.
- **Distribution and restarts:** passes, completed passes, goal kicks, pass
  completion percentage and mean pass length.

The `goalkeeper_saves` count uses the StatsBomb Stats Portal definition:
Goal Keeper events whose type is `Penalty Saved`, `Penalty Saved to Post`,
`Shot Saved`, `Shot Saved Off Target` or `Shot Saved to Post`
([StatsBomb glossary](https://stats-portal.statsbomb.com/glossary)). Other
goalkeeper action types are counted separately. StatsBomb documentation notes
that goalkeeper event records can represent an attempted action and do not
necessarily mean the attempt succeeded; these counts are therefore event
counts, not automatic success counts.

Raw counts are retained. Count metrics receive per-90 values only when the
player record contains rates calculated from complete, positive verified
minutes. Save percentage, post-shot xG/goals prevented, cross-claim rate and
long-ball accuracy remain unavailable until their denominators and underlying
event classifications are validated. The profile does not produce a
goalkeeper rating or ranking.

### ST profile metric groups

The importer produces a striker/centre-forward profile under
`role_profiles.ST`. It selects source labels that contain `Striker`, or
contain `Forward` together with `Center`/`Centre`. Labels containing
`Wing` are excluded. This includes source labels such as `Center Forward`,
`Left Center Forward`, `Right Center Forward`, and striker variants. A label
such as `Left Forward` alone is not enough evidence to classify a central
striker. Original position labels remain visible on each player row.

The profile groups existing event metrics into four sections:

- **Finishing and shot output:** shots, goals and xG.
- **Chance creation and combination:** shot assists, assists and through balls.
- **Link play and ball retention:** pass attempts/completions, carries and
  dribbles; pass completion percentage and mean pass length remain contextual.
- **Pressing and defensive contribution:** pressures, tackle-type duels,
  interceptions and ball recoveries.

Raw counts are retained. Count metrics and xG receive per-90 values only when
the player record contains rates calculated from complete, positive verified
minutes. Touches in the penalty area, aerial-duel success and calibrated
finishing efficiency are explicitly unavailable in this version; they are
not inferred from shots, goals or generic duel counts. The profile does not
produce a striker rating or ranking.

### CM profile metric groups

The importer produces a central-midfielder profile under `role_profiles.CM`.
It selects source position labels that contain `Midfield` and are either
explicitly centre-labelled (`Center`/`Centre`) or exactly the generic
`Defensive Midfield`, `Attacking Midfield` or `Central Midfield` labels.
Side midfield and wide-midfield labels are not included by this rule.

The profile groups existing event metrics into three sections:

- **Passing and progression:** pass attempts/completions, through balls,
  carries and dribbles. Pass completion percentage and mean pass length remain
  contextual fields.
- **Chance creation and attacking contribution:** shot assists, assists,
  crosses, shots, goals and xG.
- **Defensive work:** pressures, tackle-type duels, interceptions, ball
  recoveries, clearances and blocks.

Raw counts are retained. Count metrics and xG receive per-90 values only when
the player record contains rates calculated from complete, positive verified
minutes. The groups do not measure scanning, pressure resistance, positional
discipline or decision quality and do not produce a rating or ranking.

### FB profile metric groups

The importer also produces a full-back/wing-back profile under
`role_profiles.FB`. It includes players whose selected-sample position labels
end in `Back` or `Fullback`, excluding labels containing `Center Back` or
`Centre Back`. The source labels remain visible on each player row; this
selection does not infer a single primary role.

The profile groups the existing event metrics into three sections:

- **Chance creation and attacking output:** crosses, through balls, shot
  assists, assists, shots, goals and xG.
- **Distribution and progression:** pass attempts/completions, carries and
  dribbles. Pass completion percentage and mean pass length remain contextual
  fields rather than per-90 rates.
- **Defensive activity:** pressures, tackle-type duels, interceptions, ball
  recoveries, clearances and blocks.

Raw counts are retained. Count metrics and xG receive per-90 values only when
the selected-sample player record contains rates calculated from complete,
positive verified minutes. This is a descriptive profile, not a rating or
ranking. It does not measure overlapping runs, defensive positioning, crossing
quality or tactical responsibility.

### CB profile safeguards

### CB profile metric groups

The centre-back profile now groups the existing event metrics into three
descriptive sections:

- **Distribution and progression:** pass attempts/completions, crosses,
  through balls, shot assists and carries. Pass completion percentage and
  mean pass length remain contextual fields, not per-90 rates.
- **Defensive activity:** pressures, tackle-type duels, interceptions and
  ball recoveries.
- **Box protection:** clearances and blocks.

Each group exposes raw counts and includes per-90 counts only when the source
player record contains per-90 values derived from complete, positive verified
minutes. The grouping is a presentation aid; it does not calculate a role
score, rank or action-quality grade.

Aerial-duel success remains explicitly unavailable until duel event
classification and outcomes have been separately validated against the source
records. It must not be inferred from generic duel counts.

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


### Match context metadata

Each match report now exposes the source-provided context fields when present:
kick-off time, competition stage, match week, match status, stadium, referee,
and home/away group labels. The `source_field_availability` map indicates
which of these fields were actually supplied for that match.

The listed home/away score is validated as a pair of non-negative integers
before a result label and home goal difference are derived. Incomplete or
invalid score data leaves the derived result and goal difference unavailable;
the importer does not fill missing values.

This is match-level metadata, not a player-performance adjustment. It does
not reconstruct event-time score state, possession, opponent strength,
pressing opportunities, or score effects on player actions. Those require
separately validated event-level logic and must not be inferred from the final
score alone.



### Time spent in match score states

The match-level `match_context.score_state_timeline.durations` object reports
whole-second duration totals for the home and away teams in `leading`,
`drawing` and `trailing` states. It is calculated from the validated
goal-by-goal timeline and period-local match-clock fields, from each
`Half Start` event through its corresponding `Half End`. Half-time and
between-period breaks are excluded, and period 5 penalty shootouts are not
included.

Duration output is `validated` only when the score timeline is reconciled,
the existing match-clock/minutes validation succeeds, and each included
period has one usable start and end boundary. If clock or boundary evidence
is incomplete or contradictory, duration values remain unavailable.

These are team-level state durations only. They are not yet player-specific
minutes: substitutions and temporary player-off intervals have not been
intersected with score-state intervals. Do not use team durations as a
player's denominator for score-state per-90 calculations.

### Player actions by match score state

For matches whose event-time score timeline is validated against the listed final
score, player-attributed events are grouped by the player's own team's state
immediately before the event: `leading`, `drawing` or `trailing`. The goal
event itself is assigned to the state that existed immediately before that
goal; subsequent events use the updated score.

The `score_state_analysis` object is available on each match-level player row
and on selected-sample player totals. It includes raw event counters and summed
source xG for each state, plus classified/unclassified event counts and match
coverage statuses. An event is not classified when its team cannot be mapped to
the match's home/away team, its event order cannot be resolved, or the match
score timeline is not validated.

These values are raw totals, not rates or scores. They are not adjusted for
minutes spent in each state, possession, opponent, game phase or role. A player
may spend very different amounts of time leading, drawing and trailing, so raw
counts across states must not be interpreted as a per-minute performance
comparison. Score-state minutes and per-90 comparisons are not yet calculated.

### Event-time score-state timeline

Each match report now includes a `match_context.score_state_timeline` block.
The timeline reads goal events in `period` then `index` order and records
the score and each team's leading/drawing/trailing state immediately after
each goal. The listed final score is used as a reconciliation check, not as a
source for inventing missing goal events.

A scoring event is counted when it is a `Shot` with `shot.outcome = Goal`,
or an `Own Goal For` event. The corresponding `Own Goal Against` record is
not counted as a second goal. Period 5 penalty-shootout events are excluded
from the match score timeline.

The timeline is marked `validated` only when event ordering fields are
usable, scoring teams can be resolved to the match's home/away teams, and the
reconstructed score equals the listed final score. Missing/ambiguous fields
produce `unavailable`; a score disagreement produces
`reconciliation_mismatch`. Consumers must not use an unvalidated timeline
to classify player actions.

This first step provides goal-by-goal match state only. It does not yet label
each player event as occurring while their team was leading, drawing or
trailing, and it does not calculate possession-adjusted or score-adjusted
performance metrics.


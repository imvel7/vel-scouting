# StatsBomb Open Data import proof

This is the first data-ingestion proof for Vel Scout's data-driven scouting MVP.

It reads the official public StatsBomb Open Data JSON hierarchy, downloads a
small selected sample, caches raw JSON locally, validates the structure and
produces a JSON quality report plus a player-level CSV summary. It does not
download match video, access private endpoints, bypass authentication, or
write to Supabase.

## Important source boundary

StatsBomb describes this release as intended for research projects and genuine
interest in football analytics. If analysis is published/shared/distributed,
the source must be attributed to StatsBomb and its media-pack logo used.
This prototype does not establish a commercial licence for Vel Scout.

Source: https://github.com/hudl/open-data

## Install

Python 3.10+; no third-party package is required.

## First sample

From the repository root:

    python vision/statsbomb_open_data/import_open_data.py

Defaults:
- competition: FIFA World Cup (competition_id 43)
- season: 2022 (season_id 106)
- matches: first available match in chronological order
- raw JSON cache: .cache/statsbomb-open-data/raw
- report: .cache/statsbomb-open-data/reports/import-report.json
- player CSV: same directory, import-report.players.csv

The default is one match to keep the first run small. To choose a specific
match, repeat --match-id:

    python vision/statsbomb_open_data/import_open_data.py \
      --competition-id 43 --season-id 106 \
      --match-id 3869519 --match-id 3869685

To select the first five matches in a competition/season file:

    python vision/statsbomb_open_data/import_open_data.py \
      --competition-id 43 --season-id 106 --limit 5

Use --force to refresh already cached source files. Each source file's byte
count, SHA-256 and cache/download status are recorded in the output report.

## Tests

The StatsBomb importer unit tests run in GitHub Actions on relevant pushes and pull requests.

    python -m unittest discover -s vision/statsbomb_open_data -p 'test_*.py'

Tests use small synthetic event/lineup fixtures and do not claim the live
remote download was executed by the test suite.

## Metrics currently produced

The general player summary includes:
- passes attempted/completed and completion percentage;
- mean pass length where supplied;
- crosses, through balls, assists and shot assists;
- carries;
- shots, goals and sum of StatsBomb xG where supplied;
- pressures, interceptions, recoveries, clearances, blocks, tackles and dribbles.

The JSON report also contains `role_profiles.CB`, a centre-back event profile
for players whose lineup/event position labels contain "Center Back". It
exposes separate sample totals for:
- attributed events;
- pass attempts, completions, completion percentage and mean pass length;
- carries;
- pressures, interceptions and ball recoveries;
- clearances, blocks and tackles.

This CB profile is a descriptive event summary only. It does not calculate a
defensive rating, weighted score, percentile, ranking or per-90 value.

Completed passes are represented by the absence of `pass.outcome` in the
StatsBomb event schema.

## Score-state per-90 metrics

For each player, event counts and summed source xG can be normalized separately
for periods when their team is leading, drawing or trailing. Each rate uses
that player's verified on-pitch seconds in the same score state, not the
team's total duration or the player's full-match minutes.

Rates are emitted only when the match score timeline, player-minute timeline
and player event-state classification all validate. A score state with zero
verified player minutes has a null per-90 value. For multi-match summaries,
raw state metrics and state minutes are summed first; rates are then
recalculated from those combined totals. If any selected match record is
incomplete or unvalidated, aggregate score-state per-90 values remain
unavailable rather than silently omitting that match.

These rates describe event frequency in context. They are not positional
ratings, quality scores or transfer recommendations.

## Intentionally not produced yet

- percentiles or peer rankings;
- a definitive positional rating, potential score or transfer recommendation;
- off-ball positioning, scanning, body orientation, communication or other
  video-only observations.

Missing fields remain null; they are not silently converted to zero. The
first run is an ingestion and data-quality proof, not a finished scouting
report.

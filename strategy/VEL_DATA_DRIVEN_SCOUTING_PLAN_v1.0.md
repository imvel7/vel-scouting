# Vel Scout — Data-Driven Scouting Plan v1.0

**Decision date:** 12 November 2026  
**Product direction:** Data-driven player performance scouting  
**Status:** Importer v0.1 and CB event profile v0.1 are in `main`; 10 synthetic/integration tests pass and real three-match player/CB aggregation passed in GitHub Actions. No Supabase ingestion schema or commercial data licence is claimed.

## 1. Product decision

Vel Scout's primary product will no longer depend on an AI system independently watching full-match broadcasts.

The core product will collect, normalize and analyse structured football data. It will produce evidence-linked assessments of a player's current performance, role and statistical tendencies. Video/computer-vision work is postponed as a separate future research track and is not a blocker for the first working scouting product.

The product must distinguish:
- **Observed in supplied data:** a measurable event or statistic present in the dataset.
- **Calculated metric:** a reproducible value derived from those events, with its formula/version recorded.
- **Interpretation:** a cautious football explanation supported by the metrics.
- **Not observable from current data:** positioning away from the ball, scanning, body orientation, pressure resistance not captured by event data, communication, tactical discipline outside logged events, and other visual/contextual behaviours.

Vel Scout must never present an unavailable visual judgement as if it had been observed.

## 2. First working outcome

The first milestone is one complete automated player report generated from a real, openly accessible structured dataset:
1. import a competition, season and its match records;
2. import lineups/appearances and event records for selected matches;
3. calculate a small, documented set of role-relevant metrics;
4. compare the player with an appropriate peer group from the same dataset;
5. generate a report showing metrics, sample size, data coverage, source attribution and limitations.

The first report is a **current-performance data profile**, not a definitive all-round scout verdict, a potential rating, or a transfer recommendation.

## 3. Data source strategy

### Primary prototype source — StatsBomb Open Data

The public repository provides selected competition/season metadata, match lists, lineups and event JSON; selected matches also have StatsBomb 360 files. The provider describes the release as intended for research projects and genuine interest in football analytics and asks users who publish/share analysis to attribute StatsBomb and use its media-pack logo.

Use:
- as the first source for the event-data ingestion and metric-engine prototype;
- only for competitions/seasons actually present in the repository;
- with attribution preserved in every generated internal report and any permitted public research;
- without assuming that public access is a commercial licence for a future Vel Scout product.

Before public or commercial deployment, obtain a clear rights basis from the data provider or use an appropriately licensed dataset.

Official repository: https://github.com/hudl/open-data

### Dataset suitability warning — youth coverage

A live inspection of the StatsBomb `competitions.json` snapshot on 12 November 2026 found 80 competition/season records. Only one record is flagged as a youth competition: the men's FIFA U20 World Cup 1979 (competition_id 1470, season_id 274). This is not a usable contemporary youth-scouting sample.

The 2022 FIFA World Cup (competition_id 43, season_id 106) contains 64 match records and is being used only as a technical import/parser test. It is adult international football and must not be presented as evidence of current youth-player coverage.

**Decision:** StatsBomb Open Data is an engineering prototype source, not Vel Scout's youth-scouting data backbone. A separate source-selection gate must identify data with contemporary youth coverage and explicit rights for the intended Vel Scout use. Do not publish or commercialise profiles generated from the research dataset without a clear rights basis.

### Secondary technical sample — Metrica Sports Sample Data

The public sample repository describes two anonymized matches in standard CSV formats, with synchronized tracking and event data. Player/team/competition identities are anonymized. Its README asks users to acknowledge the source but does not provide a clear standalone licence statement.

Use only as a separate technical sample to test:
- tracking-data parsing;
- pitch-coordinate normalization;
- event/tracking synchronization;
- movement metrics and visualizations.

Do not use it to create named-player scouting profiles. Do not assume commercial reuse until terms are clarified.

Repository: https://github.com/metrica-sports/sample-data

### Later coverage candidate — API-Football

The current published free plan lists player, events, lineups and statistics endpoints and 100 requests/day; it also says free plans are limited by available seasons and data availability can vary. It may be tested later for a narrowly scoped coverage probe, but must not be treated as a guarantee of complete player-level data across all leagues/seasons.

Do not build the first metric engine around an unverified provider response. First make a coverage matrix for target league, season, player profile fields, appearances, minutes and match statistics. Record missing fields rather than filling them with guesses.

Pricing/coverage: https://www.api-football.com/pricing  
Terms: https://www.api-football.com/terms

### Not a core player-performance source — football-data.org Free

The published free plan lists 12 competitions, delayed scores/schedules, fixtures and league tables, with 10 calls/minute. Lineups, substitutes, goal scorers and squads appear in a separate paid "Free + Deep Data" package. This can supplement competition/match metadata, but it is not sufficient as the first detailed player-scouting data source.

Pricing: https://www.football-data.org/pricing  
Coverage: https://www.football-data.org/coverage

## 4. Implementation phases

### Phase 0 — Freeze the scope and the definitions

**Deliverable:** a compact metric dictionary for the first role and a list of fields required from the chosen dataset.

Rules:
- Start with one role only; do not attempt all seven positions at once.
- Reuse the existing role/methodology model where it fits, but do not force visual criteria into event-only analysis.
- Each metric has a name, definition, formula, unit, source event types, exclusions and known limitations.
- Keep current performance separate from potential and transfer fit.

**Exit gate:** every metric can be traced to source fields and reproduced from the same match data.

### Phase 1 — Data ingestion and normalization

**Deliverable:** a repeatable importer for the first StatsBomb Open Data sample. The initial importer is implemented at `vision/statsbomb_open_data/import_open_data.py`.

Canonical entities to map into the existing Vel Scout data model:
- provider/dataset and source licence/attribution record;
- competition and season;
- club/team;
- match;
- player identity;
- player appearance (lineup, starting/substitute status, minutes where available);
- raw event and event qualifiers;
- import batch, source file, source version/hash and import timestamp.

Requirements:
- preserve raw source files/records separately from normalized values;
- use stable source IDs and explicit mapping tables;
- deduplicate imports safely;
- keep missing values as missing, not zero;
- record the source and import timestamp for every derived result;
- validate counts, event references, player/team links and match consistency.

**Current verification:** 9 fixture-backed tests pass in GitHub Actions. A real 2022 World Cup Final sample (match_id 3869685) was fetched and parsed successfully in an ephemeral GitHub Actions runner; it produced a non-empty report and player list. The report was not uploaded or retained, and no Supabase writes occurred. Multi-match ingestion and re-import idempotence remain to be verified.

**Exit gate:** the same dataset can be re-imported without duplicate rows and with an import validation summary.

### Phase 2 — First role-specific metric engine

**Deliverable:** a versioned metric calculator for one role, selected after inspecting which role and players have sufficient match coverage in the chosen data.

**Current implementation:** CB event profile v0.1 selects players with a centre-back position label and exposes separate raw counts for attributed events, passes, completion percentage, average pass length, carries, pressures, interceptions, ball recoveries, clearances, blocks and tackles. It does not produce a defensive rating, per-90 statistic, percentile or rank.

Candidate event-derived metrics (only where the source actually provides the fields):
- passing volume and completion;
- forward/progressive passing and progression;
- carries and ball progression;
- receptions and involvement;
- defensive actions such as tackles, interceptions, blocks and clearances;
- duels/aerial contests where recorded;
- shots and expected goals where available;
- pressures or recoveries where recorded.

Metrics should be expressed as appropriate per-90 rates and/or percentages, with definitions and denominator rules recorded. Possession-adjusted measures should only be introduced when the required team/opponent possession context is available and validated.

Do not infer:
- defensive line positioning or spacing;
- off-ball movement not represented by tracking;
- scanning, body orientation or communication;
- quality of a decision solely from the successful/unsuccessful result of one event.

**Exit gate:** calculations are covered by automated tests with known input/output examples and a metric explanation page.

### Phase 3 — Peer comparison and context

**Deliverable:** a comparison engine that makes fair, bounded comparisons.

Initial rules:
- compare players in the same role/position group;
- prefer the same competition and season;
- separate starters and substitutes or account for minutes played;
- show per-90 values, percentile and sample size together;
- prevent tiny samples from appearing as stable rankings;
- show missing coverage and do not impute unavailable metrics;
- do not rank across unrelated leagues until a defensible league/context model exists.

**Exit gate:** a user can see exactly which peer group a percentile uses and how many players/matches support it.

### Phase 4 — Evidence-linked scouting report

**Deliverable:** one draft report generated from actual imported player data.

Report sections:
1. player, team, competition and season context;
2. dataset source, data coverage, minutes and match count;
3. role-specific metric summary;
4. peer comparison;
5. data-supported strengths;
6. possible development questions (not asserted weaknesses without sufficient evidence);
7. unavailable visual/tactical dimensions;
8. confidence/coverage statement and methodology version.

Every interpretation must reference the underlying metric(s), sample and comparison group. AI may help write the explanation, but it may not invent events, measurements or observations.

**Exit gate:** every report claim can be traced to a metric calculation and source record.

### Phase 5 — Validate one real pilot end to end

**Deliverable:** one player report that can be regenerated from source data.

Checks:
- manually verify a sample of imported events against the source JSON;
- independently recalculate selected metrics;
- test missing data, substitutes, position changes and short appearances;
- confirm all percentile denominators and peer-group filters;
- verify attribution and publication restrictions;
- mark unsupported visual criteria as "not available from this dataset".

**Exit gate:** no critical data-mapping errors; reproducible metrics; transparent limitations. Only then expand to more players and competitions.

### Phase 6 — Expand coverage

After the pilot passes:
- evaluate API-Football coverage for target competitions and seasons;
- test at least one target league end-to-end before adopting the provider;
- compare player ID consistency, minutes, match coverage and stat definitions;
- add providers behind separate adapters rather than tying the application to one API;
- negotiate a licensed data-provider path if broad, stable, commercially usable player statistics are needed.

No scraping of unofficial/private endpoints and no bypassing provider access controls.

### Phase 7 — Later research track: tracking and video

Tracking/computer vision is not part of the first MVP. It may return after the event-data report is working.

Potential future uses:
- Metrica sample data for anonymized tracking pipeline experiments, subject to rights clarification;
- SoccerTrack v2 only for its separately documented gated research/technical validation scope and access approval;
- actual match video only with written permission covering processing, storage, territory, duration and commercial use.

Tracking/video may add off-ball and spatial information, but it must remain a separately licensed and testable module.

## 5. What is explicitly out of scope for the first MVP

- automatic full-match video watching;
- player detection/tracking from broadcast footage;
- claims about off-ball positioning or body language from event data alone;
- a complete global database of every player and league;
- potential ratings or transfer recommendations;
- scraping unofficial endpoints;
- public use of data whose licence only supports research/personal use.

## 6. Existing Vel Scout assets to reuse

Do not rebuild the project from zero. Reuse after a read-only schema audit:
- player, club, competition, season and match records;
- player-match associations;
- rubric/methodology versioning;
- scouting report and report-version infrastructure;
- admin authentication and staff-only access.

Before adding tables, map the actual live schema to the canonical entities in Phase 1. Avoid duplicate concepts and do not alter the existing video-rights system; it remains useful for a future authorised video module.

## 7. Immediate next task

**Find an appropriate current youth-data source and validate minutes/coverage.**

Completed in the technical prototype:
1. one real StatsBomb match import;
2. three-match aggregation for the same player;
3. CB profile selection and event summary for a defender across those three matches;
4. 10 fixture-backed tests plus the real-data smoke test in GitHub Actions.

Next:
1. inspect lineup position segments and substitution events to define a reliable minutes-played calculation; keep per-90 values null until this passes tests;
2. identify a contemporary youth-player dataset/provider with a documented licence that covers Vel Scout's intended use;
3. create a coverage matrix for target leagues, seasons, players, appearances, minutes and event/stat fields;
4. only then map the normalized records into the live Vel Scout data model. Keep StatsBomb research data isolated from commercial/public profiles until rights are settled.

Do not apply a database migration until the existing live schema and required fields are compared. The first proof can run in a reproducible local/scripted pipeline and then be integrated into Supabase once the normalized model is confirmed.

## 8. Success definition

Vel Scout's first meaningful success is not "the admin panel has more sections". It is:

**Select a player → import their available match data → calculate role-relevant metrics → compare them to a defined peer group → generate a reproducible, evidence-linked report with honest limitations.**

Until that flow works, do not expand the UI or add more documentation-only milestones.

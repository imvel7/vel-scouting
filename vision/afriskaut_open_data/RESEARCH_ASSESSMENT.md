# Afriskaut Dynasty Scouting League 2024 — research assessment

**Review date:** 15 November 2026  
**Decision:** Limited youth-player pilot and parser/metric validation candidate; not a sole or primary Vel Scout provider.

## Source and licence

The publisher's public repository describes a 2024 event-data release with JSONL event files and per-match JSON metadata, lineups, substitutions and timing information.

- Repository: https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data
- README: https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data#readme
- Licence: Apache-2.0, as declared by the repository README and GitHub repository metadata.
- Publisher announcement: https://www.linkedin.com/posts/afriskaut_pre-professional-african-football-open-data-activity-7450108442012323840-BNuP

The publisher's announcement describes the competition as a Nigerian youth league for players aged 16–19. The Apache-2.0 declaration is a useful technical-use signal, but it does not replace a separate privacy, consent, safeguarding and publication review for identifiable youth-player data. The first prototype therefore keeps player names/IDs out of research logs and does not publish named scouting profiles.

## Technical coverage observed

The probe ran in an ephemeral GitHub Actions runner and did not upload a data artifact or write to Supabase.

| Check | Result |
|---|---:|
| Matches with event files | 136 |
| Event rows | 84,214 |
| Events safely linked using same-match lineup + explicit substitution IDs | 84,193 (99.98%) |
| Event rows excluded from player metrics | 21 |
| Unique player IDs with eligible events | 725 |
| Centre-back player-match entries with eligible events | 346 |

The initial lineup-only check understated linkage because it did not include substitute players. The follow-up check reads the same match's explicit substitution metadata. The remaining 21 events are excluded rather than inferred from shirt numbers or IDs in other matches.

## Interpretation and limits

- The 99.98% figure measures event-to-player attribution only. It is not evidence that event labels are tactically complete, correctly interpreted, or a valid measure of player quality.
- This is one 2024 competition sample, not broad or recurring coverage across target leagues and seasons.
- Verified minutes and per-90 denominators have not yet been implemented and reconciled against real match records.
- Event labels must be mapped against the publisher's event-map document before they are converted into scouting metrics.
- Identifiable youth-player data must remain out of public profiles until the required privacy, consent and safeguarding review has been completed.

## Decision

Use Afriskaut as a **limited, supplementary youth-event dataset** for a controlled technical pilot after event semantics and minutes are validated. Do not use it as the platform's sole data provider, do not create public player profiles from it yet, and do not import raw data into the live Supabase project at this stage.

## Next checks

1. Compare event-map definitions with actual event JSON fields and outcomes.
2. Validate match periods, timestamps, substitutions and player minutes.
3. Build only a conservative, anonymous first-role metric sample if those checks pass.
4. Continue searching for a second source with broader league/season coverage and appropriate usage rights.

## Update — 22 November 2026

Match clocks and a conservative player-minutes calculation were validated on the real sample (aggregate counts only). Clocks are complete and ordered in 136/136 matches, but substitution records are fully consistent in only 25 of 136 matches, so minutes are produced for 1,063 of 3,169 players with events and withheld elsewhere. Details and evidence are in `ROADMAP.md` section 28. Check 2 above (periods, timestamps, substitutions and minutes) is now implemented and validated; checks 1 (event-map comparison) and 3 (anonymous first-role metric sample) remain open, and the privacy, consent and safeguarding gate is unchanged.


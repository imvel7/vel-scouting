# Vel Scout — Video Source Rights & Coverage Audit
**Review date:** 12 November 2026  
**Scope:** Publicly available provider terms and source descriptions reviewed for the Vel Scout video-source registry.  
**Important:** This is an operational source-screening record, not legal advice. A source being listed or marked reviewed does not grant Vel Scout a licence. Match availability, territory, playback continuity, account eligibility, and permitted use must be verified separately.

## Executive outcome

No reviewed public archive currently provides a general permission for Vel Scout to ingest, download, store, automatically analyse, or commercially reuse its match footage. Public viewing access and AI/commercial processing rights are separate.

For now:
- Keep UEFA.tv and TRT Spor as manual discovery/viewing references only; do not automate extraction or ingest their streams.
- Do not use SoccerNet protected match video in a commercial Vel Scout pipeline. Its video access is research/NDA-governed and explicitly non-commercial.
- Treat Hudl Wyscout as a licensed professional provider whose permitted workflows depend on the specific customer agreement. No Vel Scout licence is inferred.
- Use SoccerTrack v2 only as a separately authorised computer-vision validation dataset, not as a substitute for named-player professional scouting coverage.
- Keep Football Archive as a discovery index only; rights must be checked with the actual host/rightsholder for every destination.

## Source-by-source assessment

| Source | Verified public facts | Vel Scout disposition |
|---|---|---|
| UEFA.tv Re-Runs | UEFA grants private household viewing for non-commercial purposes. Its terms restrict copying, extraction, transfer, retransmission, distribution and commercial use. Territorial restrictions apply. | **No automated ingestion, download/storage, clipping, redistribution or commercial use.** Separate written permission would be needed for broader use. Manual scouting rights remain unconfirmed by the terms reviewed. |
| TRT Spor — Maçın Tamamı | TRT's site terms reserve rights in site videos and restrict copying, moving, quoting, republishing, archiving and commercial use absent permission. | **Do not ingest or automate.** The page title alone does not prove current playback, complete match continuity, or any scouting/AI licence. |
| Premier League Archive | Official archive offers full-match replays from historical seasons; access requires myPremierLeague sign-in. Website terms restrict commercial reuse, redistribution and database creation without prior written approval. | **Discovery/viewing only under applicable personal terms.** No automated-analysis, extraction or commercial Vel Scout permission inferred. |
| FIFA+ | Platform terms limit content use to personal, lawful, non-commercial purposes and restrict reproduction/copying/distribution outside the licence. Match-level availability is variable. | **No Vel Scout commercial or automated-processing permission inferred.** Follow the provider's account eligibility and guardian requirements; never bypass age or account restrictions. |
| TFF Official YouTube | YouTube platform terms govern platform access and automated access; those terms do not grant rights to underlying TFF or third-party footage. | **Do not download or scrape.** Embedding/viewing does not grant underlying footage processing or commercial rights. |
| SoccerNet | Protected match videos are gated by an NDA; SoccerNet states the dataset is for research and not commercial use. Model training is invited in its research context. | **Research/prototype only within the accepted dataset terms; excluded from commercial Vel Scout video processing.** |
| Hudl Wyscout | Hudl describes video/data as sourced under rights agreements for professional purposes. Access and downstream use depend on the applicable customer agreement. Hudl terms also restrict certain automated/AI access and use. | **Potential licensed-provider route only through an agreement that expressly covers Vel Scout's intended uses.** No third-party ingestion or AI rights inferred. |
| SoccerTrack v2 | Dataset documentation describes 10 full-length panoramic 4K university-level matches with tracking/action annotations and a CC BY 4.0 data licence; dataset download is gated and requires approval. It is not named-player pro/youth coverage. | **Potentially useful for CV pipeline validation after access approval and licence/attribution checks.** Not a scouting video source for real named players. |
| Metrica Sports Sample Data | The sample repository is structured tracking/event data, not a full-match video archive; no clear standalone licence was confirmed in the reviewed repository material. | **Inactive in video-source registry.** Consider separately for structured-data prototyping only after clarifying reuse terms. |
| Football Archive | Third-party index linking to external match pages; no rights-holder status or general licence established. | **Discovery index only.** Review each actual host and rightsholder independently. |

## Operational rules

1. Keep viewing access, manual scouting permission, automated analysis, commercial use, download/storage, clip extraction and redistribution as separate rights.
2. Default each right to `unknown` unless there is item-specific evidence.
3. A provider's general terms do not automatically prove that a particular match is available in Türkiye or that the video is complete.
4. Do not treat a public URL, embeddable player, account access or free viewing as permission to download, scrape, process with AI, store, clip or commercialise.
5. For licensed providers, store the exact contract/customer scope and validity period before recording any right as `granted`.
6. For research datasets, preserve the dataset-specific licence, NDA, attribution and commercial-use restrictions.
7. Re-check terms when providers update them and retain dated evidence notes.

## Primary references

- UEFA.tv Terms: https://www.uefa.com/uefatvtermsconditions/
- TRT Spor Kullanım Şartları: https://www.trtspor.com.tr/kullanim-sartlari
- Premier League Archive overview: https://www.premierleague.com/en/welcome/the-archive/overview
- Premier League Terms: https://www.premierleague.com/en/terms-and-conditions
- FIFA+ Terms: https://inside.fifa.com/terms-of-service-fifaplus
- YouTube Terms: https://www.youtube.com/t/terms
- SoccerNet FAQ: https://www.soccer-net.org/faq
- SoccerNet Data: https://www.soccer-net.org/data
- Hudl Wyscout FAQ: https://www.hudl.com/products/wyscout/faq
- Hudl Terms: https://www.wyscout.hudl.com/terms
- SoccerTrack v2 data licence: https://github.com/AtomScott/SoccerTrack-v2/blob/main/LICENSE-DATA
- Metrica Sports Sample Data: https://github.com/metrica-sports/sample-data
- Football Archive index: https://footballarchive.org/stats/full-matches/

## Next implementation gate

The source registry and admin workflow exist in the database and `admin.html`. Before connecting any automated video pipeline, obtain a written rights basis that explicitly covers the planned processing, storage, territory, duration and commercial model. Until then, keep the vision-engine work isolated to datasets whose terms expressly permit the intended research/prototype use.

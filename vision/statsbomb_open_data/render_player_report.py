#!/usr/bin/env python3
"""Render an internal Markdown player profile from a StatsBomb import JSON report."""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path

ROLES = ("CB", "FB", "CM", "W", "ST", "GK")
ROLE_NAMES = {"CB": "Centre-back", "FB": "Full-back / Wing-back", "CM": "Central midfielder", "W": "Winger", "ST": "Striker", "GK": "Goalkeeper"}
LABELS = {"pass_completion_pct": "Pass completion", "pass_length_mean": "Mean pass length", "goalkeeper_actions": "Goalkeeper actions", "goalkeeper_shots_faced": "Shots faced", "goalkeeper_goals_conceded": "Goals conceded", "goalkeeper_collections": "Collections", "goalkeeper_punches": "Punches", "goalkeeper_sweeps": "Sweeps", "goalkeeper_smotherings": "Smotherings", "goalkeeper_penalty_saves": "Penalty saves", "goalkeeper_penalties_conceded": "Penalties conceded", "goal_kicks": "Goal kicks"}
STATES = ("leading", "drawing", "trailing")

class ReportError(ValueError):
    pass

def safe(value):
    if value is None:
        return "—"
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;").strip() or "—"

def fmt(value, digits=2):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            return "—"
        if float(value).is_integer():
            return f"{int(value):,}"
        return f"{value:,.{digits}f}".rstrip("0").rstrip(".")
    return safe(value)

def load_report(path):
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"Rapor dosyası okunamadı: {exc}") from exc
    if not isinstance(data, dict) or data.get("report_type") != "statsbomb_import_quality_and_event_profile":
        raise ReportError("Bu dosya desteklenen StatsBomb import raporu değil.")
    return data

def linked_player(section, role, player_id):
    roles = section.get("roles") if isinstance(section, dict) else None
    block = roles.get(role) if isinstance(roles, dict) else None
    rows = block.get("players") if isinstance(block, dict) else None
    if not isinstance(rows, list):
        return block, None
    found = [p for p in rows if isinstance(p, dict) and str(p.get("player_id")) == str(player_id)]
    if len(found) > 1:
        raise ReportError("Aynı kaynak oyuncu ID'si raporun yardımcı bölümünde birden fazla kez bulunuyor.")
    return block, found[0] if found else None

def metric_label(key, guidance):
    item = guidance.get(key) if isinstance(guidance, dict) else None
    return safe(item.get("display_name")) if isinstance(item, dict) and item.get("display_name") else safe(LABELS.get(key, key.replace("_", " ").capitalize()))

def render_metrics(profile, player, guidance):
    groups = profile.get("metric_groups") or []
    all_values = player.get("grouped_metrics") or {}
    out = []
    if not groups:
        return ["Metrik grupları bu raporda mevcut değil."]
    for group in groups:
        if not isinstance(group, dict):
            continue
        data = all_values.get(group.get("code")) if isinstance(all_values, dict) else None
        if not isinstance(data, dict):
            continue
        parts = {k: data.get(k) if isinstance(data.get(k), dict) else {} for k in ("raw_counts", "per90_counts", "raw_rate_totals", "per90_rate_metrics", "context_metrics")}
        state = data.get("per90_by_score_state")
        keys = []
        for part in parts.values():
            keys.extend(k for k in part if k not in keys)
        if isinstance(state, dict):
            for name in STATES:
                if isinstance(state.get(name), dict):
                    keys.extend(k for k in state[name] if k not in keys)
        if not keys:
            continue
        out += [f"### {safe(group.get('label') or group.get('code'))}"]
        if group.get("description"):
            out.append(safe(group["description"]))
        out += ["", "| Metric | Total | Per 90 | Context | Leading / 90 | Drawing / 90 | Trailing / 90 |", "|---|---:|---:|---:|---:|---:|---:|"]
        for key in keys:
            context = []
            for k, prefix in (("raw_rate_totals", "raw "), ("context_metrics", ""), ("per90_rate_metrics", "/90 ")):
                if key in parts[k]:
                    context.append(prefix + fmt(parts[k][key]))
            state_values = [fmt(state[name].get(key)) if isinstance(state, dict) and isinstance(state.get(name), dict) else "—" for name in STATES]
            out.append(f"| {metric_label(key, guidance)} | {fmt(parts['raw_counts'].get(key))} | {fmt(parts['per90_counts'].get(key))} | {safe('; '.join(context) if context else '—')} | " + " | ".join(state_values) + " |")
        out.append("")
    return out or ["Gruplanmış metrik değeri bulunamadı; eksik alanlar sıfır kabul edilmedi."]

def render_peer(role_data, player_data, guidance):
    out = ["## Same-role peer context", "", "Percentiles describe event frequency in this same-role sample; they are not player-quality scores or rankings.", ""]
    if not role_data or not player_data:
        return out + ["Peer comparison is unavailable in this report.", ""]
    out += [f"- Eligible role cohort: {fmt(role_data.get('eligible_player_count'))}/{fmt(role_data.get('profile_player_count'))}.", f"- Minimum minutes: {fmt(role_data.get('minimum_verified_minutes'))}; minimum cohort: {fmt(role_data.get('minimum_cohort_size'))}.", f"- Player eligible: {fmt(player_data.get('eligible_for_peer_comparison'))}."]
    if player_data.get("eligibility_reasons"):
        out.append("- Eligibility limits: " + ", ".join(safe(x) for x in player_data["eligibility_reasons"]) + ".")
    out += ["", "| Metric | Player / 90 | Percentile | Cohort n | Difference vs median | Middle 50% | Status |", "|---|---:|---:|---:|---:|---|---|"]
    for key, item in (player_data.get("metrics") or {}).items():
        if not isinstance(item, dict):
            continue
        ready = item.get("status") == "ready" and item.get("percentile") is not None
        out.append(f"| {metric_label(key, guidance)} | {fmt(item.get('value_per90'))} | {fmt(item.get('percentile'), 1) if ready else 'Not available'} | {fmt(item.get('cohort_size'))} | {fmt(item.get('difference_from_median_per90')) if ready else '—'} | {fmt(item.get('within_cohort_middle_50_percent') if ready else None)} | {'ready' if ready else safe(item.get('status'))} |")
    summaries = role_data.get("metric_summaries") or {}
    if summaries:
        out += ["", "Metric cohort thresholds:"]
        out += [f"- {metric_label(k, guidance)}: {safe(v.get('status'))}; {fmt(v.get('eligible_values'))}/{fmt(v.get('minimum_required'))} values." for k, v in summaries.items() if isinstance(v, dict)]
    out += ["", *[f"- {safe(x)}" for x in (role_data.get("interpretation_limits") or [])], ""]
    return out

def render_player_report(report, player_id, role):
    if not isinstance(report, dict) or report.get("report_type") != "statsbomb_import_quality_and_event_profile":
        raise ReportError("Geçerli bir StatsBomb import raporu gerekli.")
    if role not in ROLES:
        raise ReportError(f"Desteklenmeyen rol: {role}; roller: {', '.join(ROLES)}")
    profile = (report.get("role_profiles") or {}).get(role)
    rows = profile.get("players") if isinstance(profile, dict) else None
    if not isinstance(rows, list):
        raise ReportError(f"{role} rol profili bulunamadı.")
    found = [p for p in rows if isinstance(p, dict) and str(p.get("player_id")) == str(player_id)]
    if not found:
        raise ReportError(f"Kaynak oyuncu ID'si {player_id!r}, {role} rolünde yok; isimle eşleştirme yapılmaz.")
    if len(found) != 1:
        raise ReportError("Oyuncu ID'si rol profilinde birden fazla kez var; belirsiz kayıt.")
    player = found[0]
    benchmarks = report.get("role_benchmarks") or {}
    benchmark_role, benchmark_player = linked_player(benchmarks, role, player_id)
    _, readiness = linked_player(report.get("player_evaluation_readiness"), role, player_id)
    guidance = benchmarks.get("metric_guidance") or {}
    quality, consistency, identity = player.get("data_quality") or {}, player.get("data_consistency") or {}, player.get("identity") or {}
    state_context = player.get("score_state_context") or {}
    comp, sample, source = report.get("competition_season") or {}, report.get("sample") or {}, report.get("source") or {}
    lines = [f"# {safe(player.get('player_name'))} — {safe(profile.get('role_name') or ROLE_NAMES[role])}", "", "> Internal research report from a selected StatsBomb Open Data sample. Not a public player profile or a completed scouting verdict.", "", "## Player and sample", "", f"- Source player ID: {safe(player.get('player_id'))}.", f"- Team(s): {safe(', '.join(player.get('team_names') or []))}.", f"- Position labels: {safe(', '.join(player.get('positions_seen') or []))}.", f"- Competition / season: {safe(comp.get('competition_name'))} / {safe(comp.get('season_name'))}.", f"- Sample: {fmt(sample.get('selected_match_count'))} selected of {fmt(sample.get('available_matches_in_season_file'))} listed matches; {fmt(sample.get('event_count'))} events.", f"- Players listed/seen: {fmt(sample.get('unique_players_listed_or_seen'))}; event actors missing from lineups: {fmt(sample.get('event_players_missing_from_lineups'))}.", f"- Selected match IDs: {safe(', '.join(str(x) for x in (sample.get('selected_match_ids') or [])))}.", f"- Appearance evidence: {fmt(player.get('matches_with_appearance_evidence'))} matches; squad listings: {fmt(player.get('matches_listed_in_squads'))}.", f"- Verified minutes: {fmt(player.get('minutes_played'))}.", f"- Generated at: {safe(report.get('generated_at'))}.", "", "## Data reliability and review readiness", "", f"- Data quality: **{safe(quality.get('status'))}**.", f"- Match-to-aggregate consistency: **{safe(consistency.get('status'))}**.", f"- Source identity consistency: **{safe(identity.get('status'))}**.", f"- Possible same-name collision: **{fmt(identity.get('possible_same_name_collision'))}**.", f"- Score-state per-90: **{safe(state_context.get('per90_status'))}**; player-minute validation: **{safe(state_context.get('minutes_status'))}**."]
    for label, values in (("Data-quality reasons", quality.get("reasons")), ("Consistency reasons", consistency.get("reasons")), ("Identity review reasons", identity.get("reasons"))):
        if values:
            lines.append(f"- {label}: " + ", ".join(safe(x) for x in values) + ".")
    if readiness:
        lines.append(f"- Human-review readiness: **{safe(readiness.get('readiness_status'))}** (data sufficiency, not a player rating).")
        if readiness.get("reason_codes"):
            lines.append("- Readiness limits: " + ", ".join(safe(x) for x in readiness["reason_codes"]) + ".")
        lines.append(f"- Peer context: **{safe(readiness.get('peer_context_status'))}**.")
    lines += ["", "## Role-specific event profile", "", "Counts and rates describe recorded events; missing values remain unavailable, not zero.", ""]
    lines += render_metrics(profile, player, guidance)
    lines += render_peer(benchmark_role, benchmark_player, guidance)
    lines += ["## Source provenance", "", f"- Dataset: {safe(source.get('name'))}.", f"- Repository: {safe(source.get('repository'))}.", f"- Attribution required for shared analysis: **{fmt(source.get('attribution_required_for_shared_analysis'))}**."]
    if source.get("usage_note"):
        lines.append(f"- Usage boundary: {safe(source.get('usage_note'))}.")
    for item in report.get("source_files") or []:
        if isinstance(item, dict):
            lines.append(f"- Source file {safe(item.get('path'))}: SHA-256 {safe(item.get('sha256'))}; {fmt(item.get('bytes'))} bytes; cache {safe(item.get('cache'))}.")
    limitations = []
    for group in (report.get("limitations"), profile.get("interpretation_limits"), profile.get("not_yet_available"), (benchmark_role or {}).get("interpretation_limits")):
        if isinstance(group, list):
            for value in group:
                value = value.get("reason") if isinstance(value, dict) else value
                if value and safe(value) not in limitations:
                    limitations.append(safe(value))
    lines += ["", "## Interpretation limits", ""] + [f"- {x}" for x in limitations]
    lines += ["", "## What this report does not claim", "", "- No overall player rating, rank, potential score or transfer recommendation is assigned.", "- Higher event volume does not automatically mean better performance; metric meaning and tactical context matter.", "- Event data cannot assess off-ball positioning, scanning, body orientation, communication or visual behaviour.", "- This selected research sample does not establish broad competition coverage or commercial/publication rights.", "- Do not publish this report or create a public player profile without a separately verified data-rights and privacy basis.", ""]
    return "\n".join(lines)

def write_report(markdown, output_path, overwrite=False):
    target = Path(output_path).expanduser()
    if target.exists() and not overwrite:
        raise ReportError(f"Çıktı zaten var; üzerine yazmak için --overwrite kullan: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    return target

def main(argv=None):
    parser = argparse.ArgumentParser(description="StatsBomb JSON verisinden iç kullanım oyuncu raporu üret.")
    parser.add_argument("report_json")
    parser.add_argument("--player-id", required=True)
    parser.add_argument("--role", required=True, choices=ROLES)
    parser.add_argument("--output", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        output = write_report(render_player_report(load_report(args.report_json), args.player_id, args.role), args.output, args.overwrite)
    except ReportError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2
    print(f"Oyuncu performans raporu oluşturuldu: {output}")
    print("İç kullanım/araştırma çıktısıdır; kamuya açık yayın veya oyuncu puanı değildir.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

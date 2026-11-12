#!/usr/bin/env python3
"""Validate a locally authorized SoccerTrack v2 dataset release.

This tool only reads metadata/annotation JSON and, optionally, video stream
metadata through ffprobe. It does not download, upload, transcode, or modify data.
Large GSR JSON files are parsed incrementally with ijson.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterator

BAS_LABELS = (
    "Pass", "Drive", "Header", "High Pass", "Out", "Cross",
    "Throw In", "Shot", "Ball Player Block",
    "Player Successful Tackle", "Free Kick", "Goal",
)
BAS_LABEL_BY_CASEFOLD = {label.casefold(): label for label in BAS_LABELS}
GSR_TARGETS = {"info", "images.item", "annotations.item"}
VALID_ROLES = {"player", "goalkeeper", "referee", "other"}


def _finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _iter_gsr_objects(path: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield info/images.item/annotations.item maps with one JSON pass."""
    try:
        import ijson
        from ijson.common import ObjectBuilder
    except ImportError as exc:
        raise RuntimeError(
            "GSR doğrulaması için ijson gerekli. "
            "python -m pip install -r requirements-vision.txt"
        ) from exc

    current_prefix: str | None = None
    builder = None
    root_kind: str | None = None

    with path.open("rb") as stream:
        for prefix, event, value in ijson.parse(stream):
            if prefix == "" and event in {"start_map", "start_array"}:
                root_kind = event
                if root_kind == "start_array":
                    raise ValueError(
                        "GSR dosyası eski düz-dizi şemasında. "
                        "Bu araç yayımlanan info/images/annotations nesne şemasını bekliyor."
                    )

            if builder is None:
                if prefix in GSR_TARGETS and event == "start_map":
                    current_prefix = prefix
                    builder = ObjectBuilder()
                    builder.event(event, value)
                continue

            builder.event(event, value)
            if prefix == current_prefix and event == "end_map":
                obj = builder.value
                if isinstance(obj, dict):
                    yield current_prefix or "", obj
                builder = None
                current_prefix = None

    if root_kind != "start_map":
        raise ValueError("GSR kökü JSON nesnesi değil veya boş.")


def validate_gsr_file(path: Path, expected_half: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path),
        "half": expected_half,
        "size_bytes": path.stat().st_size,
        "images": 0,
        "annotations": 0,
        "annotation_types": {},
        "roles": {},
        "player_like_annotations": 0,
        "missing_image_references": 0,
        "coordinate_errors": 0,
        "image_dimensions": {},
        "declared_frame_rate": None,
        "warnings": [],
        "errors": [],
    }
    image_ids: set[str] = set()
    referenced_image_ids: set[str] = set()
    annotation_types: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    image_dimensions: Counter[str] = Counter()
    info: dict[str, Any] = {}

    try:
        for prefix, obj in _iter_gsr_objects(path):
            if prefix == "info":
                info = obj
            elif prefix == "images.item":
                image_id = obj.get("image_id")
                if image_id is not None:
                    key = str(image_id)
                    if key in image_ids:
                        result["warnings"].append(
                            f"Tekrarlanan image_id bulundu: {key}"
                        )
                    image_ids.add(key)
                    result["images"] += 1
                    width, height = obj.get("width"), obj.get("height")
                    if width is not None and height is not None:
                        image_dimensions[f"{width}x{height}"] += 1
            elif prefix == "annotations.item":
                result["annotations"] += 1
                image_id = obj.get("image_id")
                if image_id is not None:
                    referenced_image_ids.add(str(image_id))
                supercategory = str(obj.get("supercategory", "unknown"))
                annotation_types[supercategory] += 1

                attrs = obj.get("attributes") or {}
                role = attrs.get("role")
                if role is not None:
                    role = str(role).casefold()
                    roles[role] += 1
                    if role not in VALID_ROLES:
                        result["warnings"].append(
                            f"Bilinmeyen rol etiketi: {role}"
                        )

                if role in {"player", "goalkeeper"}:
                    result["player_like_annotations"] += 1
                    if obj.get("track_id") is None:
                        result["warnings"].append(
                            "Player/goalkeeper kaydında track_id eksik."
                        )
                    bbox_pitch = obj.get("bbox_pitch")
                    if not isinstance(bbox_pitch, dict):
                        result["coordinate_errors"] += 1
                    elif not (
                        _finite_number(bbox_pitch.get("x_bottom_middle"))
                        and _finite_number(bbox_pitch.get("y_bottom_middle"))
                    ):
                        result["coordinate_errors"] += 1

        if not info:
            result["errors"].append("GSR info nesnesi bulunamadı.")
        if result["images"] == 0:
            result["errors"].append("GSR images listesi boş veya bulunamadı.")
        if result["annotations"] == 0:
            result["errors"].append("GSR annotations listesi boş veya bulunamadı.")

        missing = referenced_image_ids - image_ids
        result["missing_image_references"] = len(missing)
        if missing:
            result["errors"].append(
                f"{len(missing)} annotation image_id değeri images listesinde yok."
            )

        frame_rate = info.get("frame_rate")
        if frame_rate is not None and not _finite_number(frame_rate):
            result["warnings"].append("info.frame_rate sayısal değil.")
        elif frame_rate is not None and abs(float(frame_rate) - 25.0) > 0.01:
            result["warnings"].append(
                f"Beklenen 25 FPS dışında frame_rate: {frame_rate}"
            )

        seq_length = info.get("seq_length")
        if seq_length is not None:
            try:
                if int(seq_length) != result["images"]:
                    result["warnings"].append(
                        "info.seq_length ile images kayıt sayısı farklı."
                    )
            except (TypeError, ValueError):
                result["warnings"].append("info.seq_length sayısal değil.")

        if result["coordinate_errors"]:
            result["errors"].append(
                f"{result['coordinate_errors']} player/goalkeeper anotasyonunda "
                "bbox_pitch orta-alt koordinatı eksik veya geçersiz."
            )

        result["annotation_types"] = dict(annotation_types)
        result["roles"] = dict(roles)
        result["image_dimensions"] = dict(image_dimensions)
        result["declared_frame_rate"] = info.get("frame_rate")
    except Exception as exc:
        result["errors"].append(f"GSR okunamadı: {type(exc).__name__}: {exc}")

    result["ok"] = not result["errors"]
    return result


def validate_bas_payload(data: Any, path_label: str = "<memory>") -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": path_label,
        "events": 0,
        "labels": {},
        "unknown_labels": [],
        "position_order_errors": 0,
        "warnings": [],
        "errors": [],
    }
    if not isinstance(data, dict):
        result["errors"].append("BAS kökü JSON nesnesi değil.")
        result["ok"] = False
        return result

    events = data.get("actions")
    event_key = "actions"
    if events is None:
        events = data.get("annotations")
        event_key = "annotations"
    if not isinstance(events, list):
        result["errors"].append(
            "BAS olay listesi bulunamadı (actions/annotations)."
        )
        result["ok"] = False
        return result

    counts: Counter[str] = Counter()
    previous_position: int | None = None
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            result["errors"].append(f"{event_key}[{index}] nesne değil.")
            continue
        raw_label = str(event.get("label", "")).strip()
        label = BAS_LABEL_BY_CASEFOLD.get(raw_label.casefold())
        if label is None:
            result["unknown_labels"].append(raw_label or "<empty>")
        else:
            counts[label] += 1

        try:
            position = int(event.get("position"))
            if position < 0:
                raise ValueError
        except (TypeError, ValueError):
            result["errors"].append(
                f"{event_key}[{index}] position geçerli milisaniye değil."
            )
            continue

        if previous_position is not None and position < previous_position:
            result["position_order_errors"] += 1
        previous_position = position

        if not event.get("gameTime"):
            result["warnings"].append(
                f"{event_key}[{index}] gameTime alanı boş."
            )

    result["events"] = len(events)
    result["labels"] = dict(counts)
    if result["events"] == 0:
        result["errors"].append("BAS olay listesi boş.")
    if result["unknown_labels"]:
        result["errors"].append(
            f"Bilinmeyen BAS etiketi sayısı: {len(result['unknown_labels'])}."
        )
    if result["position_order_errors"]:
        result["warnings"].append(
            f"{result['position_order_errors']} olay zaman sırası ihlali bulundu."
        )
    result["ok"] = not result["errors"]
    return result


def validate_bas_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return validate_bas_payload(data, str(path))
    except Exception as exc:
        return {
            "file": str(path),
            "ok": False,
            "errors": [f"BAS okunamadı: {type(exc).__name__}: {exc}"],
            "warnings": [],
        }


def inspect_video(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path), "ok": False, "warnings": [], "errors": []
    }
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        result["warnings"].append(
            "ffprobe bulunamadı; video metadata kontrol edilmedi."
        )
        return result
    if not path.is_file():
        result["errors"].append("Video dosyası bulunamadı.")
        return result

    command = [
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate,duration:format=duration",
        "-of", "json", str(path),
    ]
    try:
        proc = subprocess.run(command, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "ffprobe başarısız.")
        payload = json.loads(proc.stdout)
        streams = payload.get("streams") or []
        if not streams:
            raise ValueError("Video stream bulunamadı.")
        stream = streams[0]
        duration = stream.get("duration") or (payload.get("format") or {}).get("duration")
        rate_text = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
        try:
            actual_fps = float(Fraction(str(rate_text))) if rate_text and rate_text != "0/0" else None
        except (ValueError, ZeroDivisionError):
            actual_fps = None
        result.update({
            "width": stream.get("width"),
            "height": stream.get("height"),
            "avg_frame_rate": stream.get("avg_frame_rate"),
            "r_frame_rate": stream.get("r_frame_rate"),
            "duration_seconds": duration,
            "fps": actual_fps,
        })
        result["ok"] = True
    except Exception as exc:
        result["errors"].append(
            f"Video metadata alınamadı: {type(exc).__name__}: {exc}"
        )
    return result



def compare_video_gsr_metadata(video: dict[str, Any], gsr: dict[str, Any]) -> dict[str, Any]:
    """Compare actual ffprobe geometry/FPS with the dominant GSR image metadata."""
    result: dict[str, Any] = {
        "metadata_matches": True,
        "declared_geometry": None,
        "actual_geometry": None,
        "warnings": [],
    }
    dimensions = gsr.get("image_dimensions") or {}
    if dimensions:
        declared_geometry = max(dimensions.items(), key=lambda item: item[1])[0]
        result["declared_geometry"] = declared_geometry
        actual_width, actual_height = video.get("width"), video.get("height")
        if actual_width is not None and actual_height is not None:
            actual_geometry = f"{actual_width}x{actual_height}"
            result["actual_geometry"] = actual_geometry
            if actual_geometry != declared_geometry:
                result["metadata_matches"] = False
                result["warnings"].append(
                    f"GSR images geometrisi {declared_geometry}, ffprobe video geometrisi "
                    f"{actual_geometry}; görüntü koordinat dönüşümü bu metadata ile yapılmamalı."
                )

    declared_fps = gsr.get("declared_frame_rate")
    actual_fps = video.get("fps")
    if declared_fps is not None and actual_fps is not None:
        try:
            if abs(float(declared_fps) - float(actual_fps)) > 0.01:
                result["metadata_matches"] = False
                result["warnings"].append(
                    f"GSR frame_rate {declared_fps}, ffprobe FPS {actual_fps}."
                )
        except (TypeError, ValueError):
            result["warnings"].append("GSR frame_rate sayısal karşılaştırılamadı.")
    return result

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Yerel SoccerTrack v2 verisi için salt-okunur kalite kontrolü."
    )
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--video-first-half", type=Path)
    parser.add_argument("--video-second-half", type=Path)
    parser.add_argument("--output", type=Path, help="JSON raporunu bu dosyaya yaz.")
    args = parser.parse_args()

    root = args.dataset_root.expanduser().resolve()
    match_id = str(args.match_id)
    report: dict[str, Any] = {
        "dataset": "SoccerTrack v2",
        "match_id": match_id,
        "scope": "annotation/video metadata validation only",
        "warnings": [
            "Bu rapor scouting puanı veya oyuncu kimliği üretmez.",
            "BAS ikinci yarı konumu, ham dönem metadata'sı doğrulanmadan GSR karelerine eşlenmez.",
        ],
        "gsr": [],
        "bas": None,
        "videos": [],
        "errors": [],
    }

    for half, suffix in ((1, "1st"), (2, "2nd")):
        path = root / "gsr" / match_id / f"{match_id}_{suffix}.json"
        if not path.is_file():
            report["errors"].append(f"GSR dosyası bulunamadı: {path}")
            continue
        report["gsr"].append(validate_gsr_file(path, half))

    bas_path = root / "bas" / match_id / f"{match_id}_12_class_events.json"
    if not bas_path.is_file():
        report["errors"].append(f"BAS dosyası bulunamadı: {bas_path}")
    else:
        report["bas"] = validate_bas_file(bas_path)

    for path in (args.video_first_half, args.video_second_half):
        if path is not None:
            report["videos"].append(inspect_video(path.expanduser().resolve()))

    gsr_by_half = {item["half"]: item for item in report["gsr"]}
    for video_index, video in enumerate(report["videos"], start=1):
        half_gsr = gsr_by_half.get(video_index)
        if video.get("ok") and half_gsr:
            comparison = compare_video_gsr_metadata(video, half_gsr)
            video["gsr_comparison"] = comparison
            video["warnings"].extend(comparison["warnings"])

    nested_errors = []
    for item in report["gsr"]:
        nested_errors.extend(item.get("errors", []))
    if report["bas"]:
        nested_errors.extend(report["bas"].get("errors", []))
    for item in report["videos"]:
        nested_errors.extend(item.get("errors", []))
    report["errors"].extend(nested_errors)
    report["ok"] = not report["errors"]

    output_text = json.dumps(report, ensure_ascii=False, indent=2)
    print(output_text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

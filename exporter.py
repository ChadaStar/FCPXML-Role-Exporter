#!/usr/bin/env python3
"""Export Final Cut Pro titles to role-based SRT files."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


class ExporterError(Exception):
    """User-facing exporter error."""


@dataclass(frozen=True)
class Subtitle:
    """A single subtitle item."""

    start: Fraction
    end: Fraction
    text: str


@dataclass(frozen=True)
class TitleItem:
    """A parsed FCPXML title item."""

    role: str
    offset: Fraction
    duration: Fraction
    text: str


def local_name(tag: str) -> str:
    """Return an XML tag name without a namespace."""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def parse_time(value: str) -> Fraction:
    """Parse an FCPXML time value such as '1001/24000s'."""
    if not value or not value.endswith("s"):
        raise ExporterError(f"時間値が不正です: {value}")

    raw = value[:-1]
    try:
        return Fraction(raw)
    except ValueError as exc:
        raise ExporterError(f"時間値が不正です: {value}") from exc


def fraction_to_srt_time(value: Fraction) -> str:
    """Format seconds as SRT time, rounded to nearest millisecond."""
    if value < 0:
        value = Fraction(0, 1)

    total_ms = int(value * 1000 + Fraction(1, 2))
    milliseconds = total_ms % 1000
    total_seconds = total_ms // 1000
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60

    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def find_info_fcpxml(package_path: Path) -> Path:
    """Find Info.fcpxml inside an FCPXML package."""
    info_path = package_path / "Info.fcpxml"
    if not info_path.is_file():
        raise ExporterError("Info.fcpxmlが見つかりません。")
    return info_path


def resolve_input_path(input_path: Path) -> Path:
    """Resolve an .fcpxml file or .fcpxmld package to an XML file."""
    if input_path.suffix.lower() == ".fcpxmld":
        return find_info_fcpxml(input_path)
    return input_path


def parse_xml(xml_path: Path) -> ET.Element:
    """Parse an XML file and return its root element."""
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        raise ExporterError("XMLではありません。") from exc
    except OSError as exc:
        raise ExporterError(f"ファイルを読み込めません: {exc}") from exc

    root = tree.getroot()
    if local_name(root.tag) != "fcpxml":
        raise ExporterError("XMLではありません。")
    return root


def collect_frame_rates(root: ET.Element) -> Dict[str, Fraction]:
    """Collect frame rates by format id from frameDuration attributes."""
    rates: Dict[str, Fraction] = {}
    for elem in root.iter():
        if local_name(elem.tag) != "format":
            continue

        format_id = elem.get("id")
        frame_duration = elem.get("frameDuration")
        if not format_id or not frame_duration:
            continue

        duration = parse_time(frame_duration)
        if duration > 0:
            rates[format_id] = Fraction(1, 1) / duration
    return rates


def extract_text(title: ET.Element) -> str:
    """Extract joined title/text/text-style content."""
    parts: List[str] = []

    for child in title:
        if local_name(child.tag) != "text":
            continue

        for text_style in child:
            if local_name(text_style.tag) == "text-style":
                parts.append("".join(text_style.itertext()))

    text = "".join(parts).strip()
    return "\n".join(line for line in text.splitlines() if line.strip())


def iter_titles(root: ET.Element) -> Iterable[TitleItem]:
    """Yield title items that can be exported as subtitles."""
    for elem in root.iter():
        if local_name(elem.tag) != "title":
            continue

        role = elem.get("role") or elem.get("ref")
        if not role:
            continue

        offset_value = elem.get("offset")
        duration_value = elem.get("duration")
        if not offset_value or not duration_value:
            continue

        text = extract_text(elem)
        if not text:
            continue

        yield TitleItem(
            role=role,
            offset=parse_time(offset_value),
            duration=parse_time(duration_value),
            text=text,
        )


def group_subtitles_by_role(titles: Sequence[TitleItem]) -> Dict[str, List[Subtitle]]:
    """Group title items by role and normalize offsets to the first title."""
    if not titles:
        raise ExporterError("Roleがありません。")

    timeline_start = min(title.offset for title in titles)
    grouped: Dict[str, List[Subtitle]] = {}

    for title in titles:
        start = title.offset - timeline_start
        end = start + title.duration
        grouped.setdefault(title.role, []).append(
            Subtitle(start=start, end=end, text=title.text)
        )

    if not grouped:
        raise ExporterError("Roleがありません。")

    for subtitles in grouped.values():
        subtitles.sort(key=lambda item: (item.start, item.end, item.text))

    return grouped


def render_srt(subtitles: Sequence[Subtitle]) -> str:
    """Render subtitles in SubRip format."""
    blocks: List[str] = []

    for index, subtitle in enumerate(subtitles, start=1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    (
                        f"{fraction_to_srt_time(subtitle.start)} --> "
                        f"{fraction_to_srt_time(subtitle.end)}"
                    ),
                    subtitle.text,
                ]
            )
        )

    return "\n\n".join(blocks) + "\n"


def write_srt_files(
    grouped: Dict[str, List[Subtitle]],
    output_dir: Path,
) -> List[Path]:
    """Write one SRT file per role."""
    created_paths: List[Path] = []

    for role, subtitles in grouped.items():
        output_path = output_dir / f"{role}.srt"
        try:
            output_path.write_text(render_srt(subtitles), encoding="utf-8")
        except OSError as exc:
            raise ExporterError(f"書き込みに失敗しました: {output_path}") from exc
        created_paths.append(output_path)

    return created_paths


def export(input_path: Path) -> Dict[str, List[Subtitle]]:
    """Export SRT files and return grouped subtitles."""
    xml_path = resolve_input_path(input_path)
    output_dir = input_path.parent
    root = parse_xml(xml_path)
    collect_frame_rates(root)
    titles = list(iter_titles(root))
    grouped = group_subtitles_by_role(titles)
    write_srt_files(grouped, output_dir)
    return grouped


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Export FCPXML titles to role-based SRT files."
    )
    parser.add_argument("input", help="Path to .fcpxml or .fcpxmld")
    return parser


def print_success(grouped: Dict[str, List[Subtitle]], output_dir: Path) -> None:
    """Print a successful export report."""
    print("Role:")
    print()
    for role in grouped:
        print(role)

    print()
    print("Created")
    for role, subtitles in grouped.items():
        print(f"{role}.srt ({len(subtitles)} subtitles)")

    print()
    print(f"保存先: {output_dir}")
    print("Done.")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    input_path = Path(args.input).expanduser()

    try:
        grouped = export(input_path)
    except ExporterError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1

    print_success(grouped, input_path.parent)
    return 0


if __name__ == "__main__":
    sys.exit(main())

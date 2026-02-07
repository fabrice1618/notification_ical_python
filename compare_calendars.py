#!/usr/bin/env python3
"""
Compare two calendars (reference vs proposition) and display matches,
differences, and missing events.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Europe/Paris")


def load_calendar(file_path: str) -> dict:
    """Load calendar events from a JSON state file."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string to datetime object, normalizing to UTC."""
    # Handle ISO format with timezone
    if "+" in dt_str or dt_str.endswith("Z"):
        # Replace Z with +00:00 for fromisoformat
        dt_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_str)
        # Convert to UTC
        return dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    else:
        # Naive datetime, assume UTC
        return datetime.fromisoformat(dt_str)


def build_time_index(events: dict) -> dict:
    """Build an index of events by (start, end) tuple."""
    index = {}
    for uid, event in events.items():
        try:
            start = parse_datetime(event["start"])
            end = parse_datetime(event["end"])
            key = (start, end)
            if key not in index:
                index[key] = []
            index[key].append(event)
        except (ValueError, KeyError) as e:
            print(f"Warning: Could not parse event {uid}: {e}", file=sys.stderr)
    return index


def extract_keywords(title: str) -> set:
    """Extract meaningful keywords from a title for fuzzy matching."""
    # Remove common prefixes and bracketed content
    title = re.sub(r"\[.*?\]", "", title)  # [ISTP], [IRON], etc.
    title = re.sub(r"BACH\s*INGE\s*\d{4}-?\d*\s*:?", "", title, flags=re.IGNORECASE)
    title = re.sub(r"BTS\s+\w+\s+\d{4}-?\d*\s*:?", "", title, flags=re.IGNORECASE)
    title = re.sub(r"B\d\s+\w+\s+\d{2,4}\s*:?", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\d{4}-\d+", "", title)  # Year ranges like 2024-0
    title = re.sub(r"20\d{2}", "", title)  # Years like 2024, 2025
    title = re.sub(r"\s*-\s*SE\s*-\s*\d{2}-\d{2}", "", title)  # - SE - 24-25
    title = re.sub(r"\s*-\s*G\d+", "", title)  # - G1, - G2
    title = re.sub(r"\s+", " ", title).strip()

    # Extract words, lowercase, filter short ones
    words = set(w.lower() for w in re.findall(r"[a-zA-ZÀ-ÿ]{3,}", title))

    # Remove common noise words
    noise = {"cours", "formation", "groupe", "seance", "session"}
    return words - noise


def titles_match(ref_title: str, prop_title: str) -> bool:
    """Check if two titles match based on keywords."""
    ref_keywords = extract_keywords(ref_title)
    prop_keywords = extract_keywords(prop_title)

    if not ref_keywords or not prop_keywords:
        return False

    # Check if there's significant overlap
    common = ref_keywords & prop_keywords
    if not common:
        return False

    # At least 50% of keywords should match
    min_size = min(len(ref_keywords), len(prop_keywords))
    return len(common) >= min_size * 0.5


def normalize_location(location: str) -> str:
    """Normalize location for comparison."""
    if not location:
        return ""
    # Extract main location parts
    loc = location.lower()
    # Remove parentheses content for matching
    loc = re.sub(r"\(.*?\)", "", loc)
    loc = re.sub(r"\s+", " ", loc).strip()
    return loc


def locations_match(ref_loc: str, prop_loc: str) -> bool:
    """Check if two locations match (fuzzy)."""
    if not ref_loc and not prop_loc:
        return True
    if not ref_loc or not prop_loc:
        return False

    ref_norm = normalize_location(ref_loc)
    prop_norm = normalize_location(prop_loc)

    # Direct match
    if ref_norm == prop_norm:
        return True

    # One contains the other
    if ref_norm in prop_norm or prop_norm in ref_norm:
        return True

    # Extract key identifiers (room numbers, building names)
    ref_parts = set(re.findall(r"[a-zA-Z0-9]+", ref_loc.lower()))
    prop_parts = set(re.findall(r"[a-zA-Z0-9]+", prop_loc.lower()))

    # Check for common building/room identifiers
    common = ref_parts & prop_parts
    significant = {p for p in common if len(p) > 1}

    return len(significant) >= 1


def compare_events(ref_event: dict, prop_event: dict) -> list:
    """Compare two events and return list of differences."""
    differences = []

    # Compare title
    if not titles_match(ref_event.get("title", ""), prop_event.get("title", "")):
        differences.append({
            "field": "title",
            "ref": ref_event.get("title", ""),
            "prop": prop_event.get("title", ""),
        })

    # Compare location
    if not locations_match(ref_event.get("location", ""), prop_event.get("location", "")):
        differences.append({
            "field": "location",
            "ref": ref_event.get("location", ""),
            "prop": prop_event.get("location", ""),
        })

    return differences


def format_time(dt: datetime) -> str:
    """Format datetime for display."""
    local_dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(TIMEZONE)
    return local_dt.strftime("%Y-%m-%d %H:%M")


def format_time_range(start: datetime, end: datetime) -> str:
    """Format a time range for display."""
    start_local = start.replace(tzinfo=ZoneInfo("UTC")).astimezone(TIMEZONE)
    end_local = end.replace(tzinfo=ZoneInfo("UTC")).astimezone(TIMEZONE)

    if start_local.date() == end_local.date():
        return f"{start_local.strftime('%Y-%m-%d %H:%M')}-{end_local.strftime('%H:%M')}"
    else:
        return f"{start_local.strftime('%Y-%m-%d %H:%M')} - {end_local.strftime('%Y-%m-%d %H:%M')}"


def compare_calendars(
    ref_file: str,
    prop_file: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    """Compare two calendar files and return results."""
    ref_events = load_calendar(ref_file)
    prop_events = load_calendar(prop_file)

    # Build time indices
    ref_index = build_time_index(ref_events)
    prop_index = build_time_index(prop_events)

    results = {
        "ref_file": ref_file,
        "prop_file": prop_file,
        "ref_count": len(ref_events),
        "prop_count": len(prop_events),
        "matches": [],
        "modified": [],
        "missing": [],
        "extra": [],
    }

    matched_prop_keys = set()

    # Compare reference events against proposition
    for key, ref_event_list in sorted(ref_index.items()):
        start, end = key

        # Apply date filter
        if date_from and start < date_from:
            continue
        if date_to and start > date_to:
            continue

        ref_event = ref_event_list[0]  # Take first if duplicates

        if key in prop_index:
            prop_event = prop_index[key][0]
            matched_prop_keys.add(key)

            differences = compare_events(ref_event, prop_event)

            if differences:
                results["modified"].append({
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "ref_event": ref_event,
                    "prop_event": prop_event,
                    "differences": differences,
                })
            else:
                results["matches"].append({
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "event": ref_event,
                })
        else:
            results["missing"].append({
                "start": start.isoformat(),
                "end": end.isoformat(),
                "event": ref_event,
            })

    # Find extra events in proposition
    for key, prop_event_list in sorted(prop_index.items()):
        start, end = key

        # Apply date filter
        if date_from and start < date_from:
            continue
        if date_to and start > date_to:
            continue

        if key not in matched_prop_keys:
            prop_event = prop_event_list[0]
            results["extra"].append({
                "start": start.isoformat(),
                "end": end.isoformat(),
                "event": prop_event,
            })

    return results


def format_output(results: dict, summary_only: bool = False) -> str:
    """Format comparison results for display."""
    lines = []

    # Header
    lines.append(f"=== Comparaison ===")
    lines.append(f"Reference: {results['ref_file']} ({results['ref_count']} evenements)")
    lines.append(f"Proposition: {results['prop_file']} ({results['prop_count']} evenements)")
    lines.append("")

    if not summary_only:
        # Matches
        if results["matches"]:
            lines.append(f"--- Correspondances exactes ({len(results['matches'])}) ---")
            for item in results["matches"]:
                start = datetime.fromisoformat(item["start"])
                end = datetime.fromisoformat(item["end"])
                event = item["event"]
                time_str = format_time_range(start, end)
                lines.append(f"  [OK] {time_str} | {event.get('title', '')} @ {event.get('location', '')}")
            lines.append("")

        # Modified
        if results["modified"]:
            lines.append(f"--- Differences ({len(results['modified'])}) ---")
            for item in results["modified"]:
                start = datetime.fromisoformat(item["start"])
                end = datetime.fromisoformat(item["end"])
                ref = item["ref_event"]
                prop = item["prop_event"]
                time_str = format_time_range(start, end)
                diff_fields = ", ".join(d["field"] for d in item["differences"])
                lines.append(f"  [~] {time_str}")
                lines.append(f"      Ref:  {ref.get('title', '')} @ {ref.get('location', '')}")
                lines.append(f"      Prop: {prop.get('title', '')} @ {prop.get('location', '')}")
                lines.append(f"      Diff: {diff_fields}")
            lines.append("")

        # Missing
        if results["missing"]:
            lines.append(f"--- Manquants dans proposition ({len(results['missing'])}) ---")
            for item in results["missing"]:
                start = datetime.fromisoformat(item["start"])
                end = datetime.fromisoformat(item["end"])
                event = item["event"]
                time_str = format_time_range(start, end)
                lines.append(f"  [-] {time_str} | {event.get('title', '')} @ {event.get('location', '')}")
            lines.append("")

        # Extra
        if results["extra"]:
            lines.append(f"--- Extra dans proposition ({len(results['extra'])}) ---")
            for item in results["extra"]:
                start = datetime.fromisoformat(item["start"])
                end = datetime.fromisoformat(item["end"])
                event = item["event"]
                time_str = format_time_range(start, end)
                lines.append(f"  [+] {time_str} | {event.get('title', '')} @ {event.get('location', '')}")
            lines.append("")

    # Summary
    total_ref = len(results["matches"]) + len(results["modified"]) + len(results["missing"])
    match_pct = (len(results["matches"]) / total_ref * 100) if total_ref > 0 else 0

    lines.append("=== Resume ===")
    lines.append(f"Correspondances: {len(results['matches'])}/{total_ref} ({match_pct:.0f}%)")
    lines.append(f"Differences: {len(results['modified'])}")
    lines.append(f"Manquants: {len(results['missing'])}")
    lines.append(f"Extra: {len(results['extra'])}")

    return "\n".join(lines)


def output_json(results: dict) -> str:
    """Output results as JSON."""
    return json.dumps(results, indent=2, ensure_ascii=False)


def parse_date(date_str: str) -> datetime:
    """Parse a date string (YYYY-MM-DD) to datetime."""
    return datetime.strptime(date_str, "%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(
        description="Compare two calendars (reference vs proposition)"
    )

    # Positional arguments for files
    parser.add_argument(
        "ref_file",
        help="Reference calendar file (e.g., data/etat_source.json)"
    )
    parser.add_argument(
        "prop_file",
        help="Proposition calendar file (e.g., data/etat_google_source.json)"
    )

    # Options
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        help="Start date filter (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        help="End date filter (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary only"
    )

    args = parser.parse_args()

    # Validate required arguments
    if not args.ref_file or not args.prop_file:
        parser.print_help()
        sys.exit(1)

    ref_file = args.ref_file
    prop_file = args.prop_file

    # Parse date filters
    date_from = parse_date(args.date_from) if args.date_from else None
    date_to = parse_date(args.date_to) if args.date_to else None

    # Run comparison
    results = compare_calendars(ref_file, prop_file, date_from, date_to)

    # Output
    if args.json:
        print(output_json(results))
    else:
        print(format_output(results, summary_only=args.summary))


if __name__ == "__main__":
    main()

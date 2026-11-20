#!/usr/bin/env python3
"""Generate SRT subtitles from video-plan.md script table."""
import argparse
import json
import re
import sys
from pathlib import Path


def parse_time_to_seconds(time_str):
    """Parse time string MM:SS to seconds."""
    if ":" in time_str:
        parts = time_str.split(":")
        minutes = int(parts[0])
        seconds = int(parts[1])
        return minutes * 60 + seconds
    return int(time_str)


def seconds_to_srt_time(seconds):
    """Convert seconds to SRT time format HH:MM:SS,mmm."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def resolve_marker(marker_text):
    """Resolve a MEASURED marker to its value.
    
    Supports patterns:
    - "<field> from <json_path>": reads the JSON file and extracts the field
    - Other patterns: returns None (unresolved)
    """
    # Pattern: <field> from <path>
    match = re.match(r'^(.+?)\s+from\s+(.+)$', marker_text)
    if not match:
        return None
    
    field_name = match.group(1).strip()
    file_path_str = match.group(2).strip()
    
    # Resolve path relative to repository root
    file_path = Path(file_path_str)
    if not file_path.exists():
        return None
    
    # Read JSON file
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None
    
    # Extract top-level field
    if field_name in data:
        return str(data[field_name])
    
    return None


def replace_measured_markers(text):
    """Replace MEASURED markers in text with actual values."""
    # Pattern: <!-- MEASURED: ... -->
    pattern = r'<!-- MEASURED: ([^>]+) -->'
    
    unresolved = []
    
    def replace_marker(match):
        marker_text = match.group(1).strip()
        resolved = resolve_marker(marker_text)
        if resolved is not None:
            return resolved
        else:
            unresolved.append(marker_text)
            return "[MEASURED]"
    
    replaced_text = re.sub(pattern, replace_marker, text)
    
    return replaced_text, unresolved


def parse_script_table(md_path):
    """Parse the timed script table from video-plan.md."""
    content = Path(md_path).read_text()
    
    # Find the timed script table
    table_match = re.search(
        r'\| Start \| End \| Scene \| On Screen \| Narration \| Subtitle \|.*?\n\|----.*?\n((?:\|.*?\n)+)',
        content,
        re.DOTALL
    )
    
    if not table_match:
        print("ERROR: Could not find timed script table", file=sys.stderr)
        sys.exit(1)
    
    table_rows = table_match.group(1).strip().split('\n')
    
    cues = []
    all_unresolved = set()
    
    for row in table_rows:
        if not row.strip():
            continue
        
        # Parse table row: | Start | End | Scene | On Screen | Narration | Subtitle |
        cells = [cell.strip() for cell in row.split('|')]
        if len(cells) < 7:
            continue
        
        start_str = cells[1]
        end_str = cells[2]
        subtitle_text = cells[6]
        
        # Skip title card (no subtitle)
        if not subtitle_text or subtitle_text == "(silence or minimal ambient sound)":
            continue
        
        # Parse times
        start_sec = parse_time_to_seconds(start_str)
        end_sec = parse_time_to_seconds(end_str)
        
        # Handle multi-line subtitles (markdown <br> becomes newline)
        subtitle_lines = subtitle_text.replace('<br>', '\n')
        
        # Replace MEASURED markers
        replaced_text, unresolved = replace_measured_markers(subtitle_lines)
        all_unresolved.update(unresolved)
        
        cues.append({
            'start': start_sec,
            'end': end_sec,
            'text': replaced_text
        })
    
    return cues, list(all_unresolved)


def generate_srt(cues, out_path):
    """Generate SRT file from cues."""
    with open(out_path, 'w', encoding='utf-8') as f:
        for i, cue in enumerate(cues, start=1):
            f.write(f"{i}\n")
            f.write(f"{seconds_to_srt_time(cue['start'])} --> {seconds_to_srt_time(cue['end'])}\n")
            f.write(f"{cue['text']}\n")
            f.write("\n")


def validate_cues(cues):
    """Validate cues are monotonic and non-overlapping."""
    errors = []
    
    for i, cue in enumerate(cues):
        # Check monotonic
        if cue['start'] >= cue['end']:
            errors.append(f"Cue {i+1}: start {cue['start']}s >= end {cue['end']}s")
        
        # Check non-overlapping with next
        if i + 1 < len(cues):
            next_cue = cues[i + 1]
            if cue['end'] > next_cue['start']:
                errors.append(
                    f"Cue {i+1} overlaps with cue {i+2}: "
                    f"ends at {cue['end']}s but next starts at {next_cue['start']}s"
                )
    
    # Check last cue ends before 2:50
    if cues:
        last_end = cues[-1]['end']
        if last_end > 170:  # 2:50
            errors.append(f"Last cue ends at {last_end}s, exceeds 2:50 (170s)")
    
    return errors


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate SRT subtitles from video-plan.md")
    parser.add_argument(
        "--out",
        type=str,
        default=str(Path.home() / "dev" / "lazarus-recordings" / "coroner-subtitles.srt"),
        help="Output SRT file path (default: ~/dev/lazarus-recordings/coroner-subtitles.srt)"
    )
    
    args = parser.parse_args()
    
    md_path = Path("docs/video-plan.md")
    out_path = Path(args.out)
    
    if not md_path.exists():
        print(f"ERROR: {md_path} not found", file=sys.stderr)
        sys.exit(1)
    
    # Parse script table
    cues, unresolved = parse_script_table(md_path)
    
    if not cues:
        print("ERROR: No subtitle cues found in script table", file=sys.stderr)
        sys.exit(1)
    
    # Validate
    errors = validate_cues(cues)
    if errors:
        print("ERROR: Subtitle validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        sys.exit(1)
    
    # Generate
    out_path.parent.mkdir(parents=True, exist_ok=True)
    generate_srt(cues, out_path)
    
    print(f"Generated {out_path} with {len(cues)} cues")
    print(f"Duration: {cues[0]['start']}s to {cues[-1]['end']}s")
    
    # Report unresolved markers
    if unresolved:
        print(f"\nUnresolved MEASURED markers: {', '.join(unresolved)}")


if __name__ == "__main__":
    main()

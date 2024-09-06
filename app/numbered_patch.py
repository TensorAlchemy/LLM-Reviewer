import os
import re
from typing import List, Tuple, Optional

SKIPPED_FILE_TYPES: List[str] = [".lock"]


def get_file_extension(file_name: str) -> str:
    return os.path.splitext(file_name)[1].lower()


def is_skipped_file(file_name: str) -> bool:
    return get_file_extension(file_name) in SKIPPED_FILE_TYPES


def is_empty_or_numeric(line: str) -> bool:
    return not line or line.isdigit()


def remove_last_if_empty_or_numeric(lines: List[str]) -> List[str]:
    return lines[:-1] if lines and is_empty_or_numeric(lines[-1].strip()) else lines


def parse_hunk_header(header: str) -> Optional[int]:
    match = re.match(r"@@ -\d+(,\d+)? \+(\d+)(,\d+)? @@", header)
    return int(match.group(2)) - 1 if match else None


def process_hunk_header(
    line: str,
    idx: int,
    lines: List[str],
) -> Tuple[int, bool, List[str]]:
    current_line_number = parse_hunk_header(line) or 0
    numbered_lines = remove_last_if_empty_or_numeric(lines)
    numbered_lines.append(line)

    should_skip_file = False
    if len(lines) < 1:
        return current_line_number, should_skip_file, numbered_lines

    if idx > 0:
        should_skip_file = is_skipped_file(lines[idx - 1])
        if should_skip_file:
            numbered_lines.append("**FILE OMITTED FOR BREVITY**")

    return current_line_number, should_skip_file, numbered_lines


def process_line(line: str, current_line_number: int) -> Tuple[str, int]:
    if line.startswith("-"):
        return f"\t{line}", current_line_number
    else:
        return f"{current_line_number + 1}\t{line}", current_line_number + 1


def number_lines_in_patch(changes: str) -> str:
    if "@@" not in changes:
        return changes

    lines = changes.split("\n")
    numbered_lines: List[str] = []
    current_line_number: int = 0
    should_skip_file: bool = False
    found_first_chunk: bool = False

    for idx, line in enumerate(lines):
        if line.startswith("@@"):
            current_line_number, should_skip_file, numbered_lines = process_hunk_header(
                line, idx, numbered_lines
            )
            found_first_chunk = True
        elif not found_first_chunk:
            numbered_lines.append(line)
        elif should_skip_file:
            continue  # Skip all lines after "**FILE OMITTED FOR BREVITY**"
        else:
            processed_line, current_line_number = process_line(
                line, current_line_number
            )
            numbered_lines.append(processed_line)

    return "\n".join(remove_last_if_empty_or_numeric(numbered_lines))

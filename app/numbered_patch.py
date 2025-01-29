import re
from typing import List, Optional, Tuple

# Text to show when file is omitted
OMITTED_BREVITY_TEXT: str = "**FILE OMITTED FOR BREVITY**"


def is_empty_or_numeric(line: str) -> bool:
    return not line or line.isdigit()


def is_file_name(line: str) -> bool:
    return line.startswith("---") or line.startswith("+++")


def remove_last_if_empty_or_numeric(lines: List[str]) -> List[str]:
    return lines[:-1] if lines and is_empty_or_numeric(lines[-1].strip()) else lines


def parse_hunk_header(header: str) -> Optional[int]:
    match = re.match(r"@@ -\d+(,\d+)? \+(\d+)(,\d+)? @@", header)
    return int(match.group(2)) - 1 if match else None


def process_hunk_header(
    line: str,
    lines: List[str],
) -> Tuple[int, List[str]]:
    current_line_number = parse_hunk_header(line) or 0
    numbered_lines = remove_last_if_empty_or_numeric(lines)
    numbered_lines.append(line)

    if not lines:
        return current_line_number, numbered_lines

    return current_line_number, numbered_lines


def process_line(line: str, current_line_number: int) -> Tuple[str, int]:
    if line.startswith("-"):
        return f"\t{line}", current_line_number
    else:
        return f"{current_line_number + 1}\t{line}", current_line_number + 1


def number_lines_in_patch(changes: str) -> str:
    """Add line numbers to a git patch while respecting diff format.

    Returns the original string if it does not contain diff chunks ("@@").
    """
    if "@@" not in changes:
        return changes

    def process_lines(lines: List[str]) -> List[str]:
        numbered_lines: List[str] = []
        current_line_number: int = 0
        should_skip_file: bool = False
        found_first_chunk: bool = False

        for line in lines:
            if is_file_name(line):
                numbered_lines.append(line)
                continue

        if line.startswith("@@"):
            found_first_chunk = True

            current_line_number, numbered_lines = process_hunk_header(
                line, numbered_lines
            )

            if should_skip_file:
                numbered_lines.append(OMITTED_BREVITY_TEXT)
                continue

        elif should_skip_file:
            continue  # Skip all lines after "**FILE OMITTED FOR BREVITY**"

        elif not found_first_chunk:
            numbered_lines.append(line)

        else:
            processed_line, current_line_number = process_line(
                line, current_line_number
            )
            numbered_lines.append(processed_line)

    return "\n".join(remove_last_if_empty_or_numeric(numbered_lines))
    return "\n".join(
        remove_last_if_empty_or_numeric(process_lines(changes.split("\n")))
    )

import re
from typing import List, Optional, Tuple

from loguru import logger

from config import SKIP_EXTENSIONS

# Text to show when file is omitted
OMITTED_BREVITY_TEXT: str = "**FILE OMITTED FOR BREVITY**"
MAX_FILE_LINES: int = 2000  # Skip files larger than this


class DiffState:
    def __init__(self):
        self.current_line: int = 0
        self.in_file: bool = False
        self.should_skip: bool = False
        self.last_was_removal: bool = False

    def update_line_number(self, line: str) -> None:
        if line.startswith("+"):
            self.current_line += 1
            self.last_was_removal = False
        elif line.startswith("-"):
            self.last_was_removal = True
        else:  # Context line
            self.current_line += 1
            self.last_was_removal = False


def is_empty_or_numeric(line: str) -> bool:
    return not line or line.isdigit()


def check_file_size(lines: List[str]) -> bool:
    """
    Check if file exceeds maximum line limit.

    Args:
        lines: List of diff lines

    Returns:
        True if file should be skipped due to size
    """
    # Look for actual content lines, not metadata
    content_lines = [
        l for l in lines if l.startswith((" ", "+")) and not l.startswith("+++")
    ]

    # For new files (starting with @@ -0,0), only count added lines
    if any(l.startswith("@@ -0,0") for l in lines):
        content_lines = [l for l in lines if l.startswith("+")]

    current_size = len(content_lines)
    if current_size > MAX_FILE_LINES:
        logger.warning(
            f"File too large: {current_size} lines > {MAX_FILE_LINES} maximum"
        )
        return True
    return False


def is_file_name(line: str) -> bool:
    return (
        line.startswith("---")
        or line.startswith("+++")
        or line.startswith("diff --git")
    )


def remove_last_if_empty_or_numeric(lines: List[str]) -> List[str]:
    return lines[:-1] if lines and is_empty_or_numeric(lines[-1].strip()) else lines


def parse_hunk_header(header: str) -> Optional[int]:
    """Parse a diff hunk header to extract the starting line number.

    Args:
        header: The hunk header line (e.g., "@@ -1,7 +1,6 @@")

    Returns:
        Starting line number (0-based) or None if parsing fails
    """
    try:
        match = re.match(r"@@ -\d+(,\d+)? \+(\d+)(,\d+)? @@", header)
        if not match:
            return None
        return max(int(match.group(2)) - 1, 0)  # Ensure non-negative line numbers
    except (AttributeError, ValueError, IndexError):
        return None


def process_hunk_header(
    line: str,
    lines: List[str],
) -> Tuple[int, List[str]]:
    """Process a hunk header and prepare lines for numbering.

    Args:
        line: The hunk header line
        lines: Previously processed lines

    Returns:
        Tuple of (starting line number, processed lines)
    """
    if not line.startswith("@@"):
        raise ValueError("Invalid hunk header format")

    current_line_number = parse_hunk_header(line)
    if current_line_number is None:
        current_line_number = 0

    # Remove any trailing empty or numeric lines before adding new header
    numbered_lines = remove_last_if_empty_or_numeric(lines)
    numbered_lines.append(line)

    return current_line_number, numbered_lines


def process_line(line: str, state: DiffState) -> str:
    """Process a single line of the diff with proper state tracking.

    Args:
        line: The diff line to process
        state: Current diff processing state

    Returns:
        Formatted line with line number if appropriate
    """
    if line.startswith("-"):
        return f"\t{line}"
    elif line.startswith("\\"):  # No newline marker
        return f"\t{line}"
    elif line.startswith("+") or not line.startswith(("-", "\\")):
        state.update_line_number(line)
        return f"{state.current_line}\t{line}"
    else:
        return line


def extract_filename(line: str) -> str:
    """
    Extract filename from a diff header line.

    Args:
        line: A diff header line (diff --git, +++ or ---)

    Returns:
        Extracted filename or empty string if line should be skipped
    """
    if line.startswith("diff --git"):
        # Format: diff --git a/path b/path
        return line.split()[-1][2:]  # Take 'b/path' and remove 'b/'
    elif line.startswith("+++"):
        # Format: +++ b/path
        filename = line[4:].strip()  # Skip '+++ ' prefix
        if filename.startswith("b/"):
            filename = filename[2:]  # Strip b/ prefix
        return filename
    return ""  # Skip --- lines


def should_skip_file(filename: str) -> bool:
    """Check if file should be skipped based on its extension."""
    # Skip .uid files
    if filename.endswith(".uid"):
        return True

    # Get the base extension before any .uid suffix
    base_name = filename.replace(".uid", "")
    ext = base_name.split(".")[-1].lower()

    return ext in SKIP_EXTENSIONS.split(",")


def process_lines(lines: List[str]) -> List[str]:
    """Process a list of diff lines and add line numbers.

    Args:
        lines: List of strings representing diff lines

    Returns:
        List of processed lines with line numbers added

    Raises:
        ValueError: If lines is None or contains invalid diff format
    """
    if not all(isinstance(line, str) for line in lines):
        raise ValueError("Input must be a list of strings")

    numbered_lines: List[str] = []
    state = DiffState()
    found_first_chunk: bool = False

    for line in lines:
        if is_file_name(line):
            numbered_lines.append(line)
            state.in_file = True
            filename = extract_filename(line)
            state.should_skip = filename and should_skip_file(filename)
            found_first_chunk = False
            continue

        if line.startswith("@@"):
            # found_first_chunk is set in size check block

            state.current_line, numbered_lines = process_hunk_header(
                line, numbered_lines
            )

            # Check if we should skip the file
            if not found_first_chunk:
                found_first_chunk = True
                if state.should_skip or check_file_size(lines):
                    state.should_skip = True
                    numbered_lines.append(OMITTED_BREVITY_TEXT)
                    continue

            elif state.should_skip:
                numbered_lines.append(OMITTED_BREVITY_TEXT)
                continue

        elif state.should_skip:
            continue  # Skip all lines after "**FILE OMITTED FOR BREVITY**"

        elif not found_first_chunk:
            numbered_lines.append(line)

        else:
            processed_line = process_line(line, state)
            numbered_lines.append(processed_line)

    return numbered_lines


def number_lines_in_patch(changes: str) -> str:
    """Add line numbers to a git patch while respecting diff format.

    Args:
        changes: Git patch content as string

    Returns:
        Numbered patch content

    Raises:
        ValueError: If input is invalid or malformed
    """
    if not changes or "@@" not in changes:
        return changes

    try:
        lines = changes.splitlines()
        numbered_lines = process_lines(lines)
        return "\n".join(numbered_lines)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid patch format: {str(e)}")

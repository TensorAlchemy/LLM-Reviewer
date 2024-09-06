import re
from typing import List

""" Add line numbers to a patch file for the LLM """


def number_lines_in_patch(changes: str) -> str:
    """Add line numbers to a patch file for the LLM"""
    lines = changes.split("\n")
    numbered_lines: List[str] = []
    current_line_number: int = 0
    in_hunk: bool = False

    for line in lines:
        if in_hunk and is_end_of_hunk(line):
            in_hunk = False
            current_line_number = None

        if in_hunk:
            if line.startswith("-"):
                line = f"\t{line}"
            else:
                current_line_number += 1
                line = f"{current_line_number}\t{line}"

        if line.startswith("@@"):
            in_hunk = True
            current_line_number = parse_hunk_header(line)

        numbered_lines.append(line)

    return "\n".join(numbered_lines)


def parse_hunk_header(header: str) -> int:
    match = re.match(r"@@ -\d+(,\d+)? \+(\d+)(,\d+)? @@", header)
    if not match:
        raise ValueError(f"Invalid hunk header: {header}")
    return int(match.group(2)) - 1


def is_end_of_hunk(line: str) -> bool:
    return not re.match(r"[ +-]", line)


def test_number_lines_in_patch_add_code():
    input_text = """diff --git a/hello.py b/hello.py
new file mode 100755
index 0000000..5dc9fd1
--- /dev/null
+++ b/hello.py
@@ -0,0 +1,3 @@
+#!/usr/bin/env python
+
+print("Hello, world")
"""
    expected_output = """diff --git a/hello.py b/hello.py
new file mode 100755
index 0000000..5dc9fd1
--- /dev/null
+++ b/hello.py
@@ -0,0 +1,3 @@
1\t+#!/usr/bin/env python
2\t+
3\t+print("Hello, world")
"""
    assert number_lines_in_patch(input_text) == expected_output


def test_number_lines_in_patch_remove_line():
    input_text = """
diff --git a/foo/__init__.py b/foo/__init__.py
index 01234567..01234567 100644
--- a/foo/__init__.py
+++ b/foo/__init__.py
@@ -1 +0,0 @@
-
"""
    expected_output = """
diff --git a/foo/__init__.py b/foo/__init__.py
index 01234567..01234567 100644
--- a/foo/__init__.py
+++ b/foo/__init__.py
@@ -1 +0,0 @@
\t-
"""
    assert number_lines_in_patch(input_text) == expected_output


def test_number_lines_in_patch_replace_code():
    input_text = """diff --git a/hello.py b/hello.py
index 5dc9fd1..54f6661 100644
--- a/hello.py
+++ b/hello.py
@@ -1,3 +1,5 @@
-#!/usr/bin/env python
+import sys
 
 print("Hello, world")
+
+sys.exit(0)
"""
    expected_output = """diff --git a/hello.py b/hello.py
index 5dc9fd1..54f6661 100644
--- a/hello.py
+++ b/hello.py
@@ -1,3 +1,5 @@
\t-#!/usr/bin/env python
1\t+import sys
2\t 
3\t print("Hello, world")
4\t+
5\t+sys.exit(0)
"""
    assert number_lines_in_patch(input_text) == expected_output


def test_number_lines_in_patch_add_single_line():
    input_text = """diff --git a/test.py b/test.py
new file mode 100644
index 0000000..11b15b1
--- /dev/null
+++ b/test.py
@@ -0,0 +1 @@
+print("hello")
"""
    expected_output = """diff --git a/test.py b/test.py
new file mode 100644
index 0000000..11b15b1
--- /dev/null
+++ b/test.py
@@ -0,0 +1 @@
1\t+print("hello")
"""
    assert number_lines_in_patch(input_text) == expected_output

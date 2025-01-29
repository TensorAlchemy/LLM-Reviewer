from typing import List

from app.numbered_patch import (
    MAX_FILE_LINES,
    DiffState,
    check_file_size,
    extract_filename,
    is_file_name,
    number_lines_in_patch,
    parse_hunk_header,
    process_line,
    should_skip_file,
)


def compare_results(expected_output: str, actual_output: str, error: str) -> None:
    split_actual: List[str] = actual_output.split("\n")
    split_expected: List[str] = expected_output.split("\n")

    to_iter: int = len(split_actual)

    for idx in range(to_iter):
        assert split_expected[idx] == split_actual[idx], error


def test_extract_filename():
    assert extract_filename("diff --git a/src/file.py b/src/file.py") == "src/file.py"
    assert extract_filename("+++ b/src/test.py") == "src/test.py"
    assert extract_filename("--- a/old.py") == ""  # Skip --- lines


def test_check_file_size():
    small_file = [
        "diff --git a/small.py b/small.py",
        "@@ -1,3 +1,5 @@",
        " import sys",
        "+x = 1",
        " y = 2",
    ]
    assert not check_file_size(small_file)

    large_file = [" line " + str(i) for i in range(MAX_FILE_LINES + 1)]
    assert check_file_size(large_file)


def test_is_file_name():
    assert is_file_name("diff --git a/file.py b/file.py")
    assert is_file_name("+++ b/test.py")
    assert is_file_name("--- a/old.py")
    assert not is_file_name(" Some regular line")
    assert not is_file_name("+added line")


from unittest.mock import patch


@patch("app.numbered_patch.SKIP_EXTENSIONS", "jpg,json,gz")
def test_should_skip_file():
    assert should_skip_file("package-lock.json"), "Should skip json files"
    assert should_skip_file("file.jpg"), "Should skip jpg files"
    assert should_skip_file("archive.tar.gz"), "Should skip tar.gz files"
    assert not should_skip_file("code.py"), "Should not skip py files"
    assert not should_skip_file("test.txt"), "Should not skip txt files"


def test_process_line():
    state = DiffState()

    # Test removal line
    assert process_line("-removed line", state) == "\t-removed line"
    assert state.current_line == 0  # Line number shouldn't increment

    # Test addition line
    assert process_line("+added line", state) == "1\t+added line"
    assert state.current_line == 1

    # Test context line
    assert process_line(" context", state) == "2\t context"
    assert state.current_line == 2


def test_parse_hunk_header():
    assert parse_hunk_header("@@ -1,7 +1,6 @@") == 0
    assert parse_hunk_header("@@ -0,0 +1,3 @@") == 0
    assert parse_hunk_header("@@ -1 +2 @@") == 1
    assert parse_hunk_header("invalid") is None


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
    compare_results(
        expected_output,
        number_lines_in_patch(input_text),
        "Numbers were not added to patch",
    )


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
    compare_results(
        expected_output,
        number_lines_in_patch(input_text),
        "Numbers were not added when removing a line",
    )


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
    compare_results(
        expected_output,
        number_lines_in_patch(input_text),
        "Numbers were not added when replacing code",
    )


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
    compare_results(
        expected_output,
        number_lines_in_patch(input_text),
        "Adding a single line was not numbered",
    )


def test_no_lock_files():
    input_text = """diff --git a/package-lock.json b/package-lock.json
index 5dc9fd1..54f6661 100644
--- a/hello.py
+++ b/hello.py
@@ -1,3 +1,5 @@
-#!/usr/bin/env python
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,3 +1,5 @@
    SOME REALLY
    REALLY REALLY
    REALLY REALLY
    REALLY REALLY
    REALLY REALLY
-   REALLY REALLY
    REALLY REALLY
+   LONG STRING
--- /dev/null
+++ b/test.py
@@ -0,0 +1 @@
"""
    expected_output = """diff --git a/package-lock.json b/package-lock.json
--- a/hello.py
+++ b/hello.py
@@ -1,3 +1,5 @@
\t-#!/usr/bin/env python
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,3 +1,5 @@
**FILE OMITTED FOR BREVITY**
--- /dev/null
+++ b/test.py
@@ -0,0 +1 @@
"""
    print(number_lines_in_patch(input_text))
    compare_results(
        expected_output,
        number_lines_in_patch(input_text),
        "Package lock files were not removed for brevity",
    )

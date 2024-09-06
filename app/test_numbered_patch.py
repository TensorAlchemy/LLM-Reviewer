from typing import List

from app.numbered_patch import number_lines_in_patch


def compare_results(expected_output: str, actual_output: str, error: str) -> None:
    split_actual: List[str] = actual_output.split("\n")
    split_expected: List[str] = expected_output.split("\n")

    to_iter: int = len(split_actual)

    for idx in range(to_iter):
        assert split_expected[idx] == split_actual[idx], error


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
index 5dc9fd1..54f6661 100644
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

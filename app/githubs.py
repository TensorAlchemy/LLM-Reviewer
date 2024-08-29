#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import json
import os
import re
import traceback
from typing import Tuple

import requests
from github import Github


# List of event types
EVENT_TYPE_PUSH = "push"
EVENT_TYPE_COMMENT = "comment"
EVENT_TYPE_PULL_REQUEST = "pull_request"
EVENT_TYPE_OTHER = "other"


class GithubClient:
    """Github API client"""

    def __init__(
        self,
        llm_client,
        review_per_file=False,
        comment_per_file=False,
        blocking=False,
    ):
        self.llm_client = llm_client
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_client = Github(self.github_token)
        self.review_tokens = (
            self.llm_client.max_tokens - self.llm_client.min_tokens
        )
        self.review_per_file = review_per_file
        self.comment_per_file = comment_per_file
        self.blocking = blocking

    def get_event_type(self, payload) -> str:
        """Determine the type of event"""
        if payload.get("head_commit") is not None:
            return EVENT_TYPE_PUSH

        if payload.get("pull_request") is not None:
            return EVENT_TYPE_PULL_REQUEST

        if payload.get("comment") is not None:
            return EVENT_TYPE_COMMENT

        return EVENT_TYPE_OTHER

    def get_pull_request(self, payload):
        """Get the pull request"""
        repo = self.github_client.get_repo(os.getenv("GITHUB_REPOSITORY"))
        pr = repo.get_pull(payload.get("number"))
        changes = requests.get(
            pr.url,
            timeout=30,
            headers={
                "Authorization": "Bearer " + self.github_token,
                "Accept": "application/vnd.github.v3.diff",
            },
        ).text
        return pr, changes

    def cut_changes(self, previous_filename, filename, patch):
        """Cut the changes to fit the max tokens"""
        if previous_filename is None:
            previous_filename = filename

        # add a patch header
        patch = f"diff --git a/{previous_filename} b/{filename}\n{patch}"
        if self.llm_client.count_tokens(patch) < self.review_tokens:
            return patch

        # TODO: it is not a good idea to cut the contents, need figure out a better way
        lines = patch.splitlines()
        print(
            f"The changes for {filename} is too long, contents would be cut to fit the max tokens"
        )
        i = len(lines)
        while i > 0:
            i -= 1
            line = "\n".join(lines[:i])
            if self.llm_client.count_tokens(line) < self.review_tokens:
                return line
        return ""

    def get_completion(self, prompt) -> Tuple[str, str]:
        """Get the completion text and cost"""
        try:
            completion_text, cost = self.llm_client.get_completion(prompt, json=True)
            return completion_text, cost
        except Exception as e:
            if self.blocking:
                raise e
            else:
                print(
                    f"The LLM failed on prompt with exception: {e}\n{traceback.format_exc()}"
                )
                return ""

    def delete_old_comments(self, pr, attempt=1):
        """Delete old comments on the PR created by the bot"""

        # Comments API returning paged data, so need to iterate few times to make sure
        # that all comments are deleted
        max_num_of_delete_steps = 16
        for i in range(max_num_of_delete_steps):
            print(f"Deleting old comments [{i}]")
            # Integration has no permission to get_user
            # github_action_bot_username = self.github_client.get_user().login
            comments = list(pr.get_issue_comments())
            for comment in comments:
                # Make sure only touch our bot's comments
                if not comment.user.login.startswith("github-actions"):
                    continue

                try:
                    comment.delete()
                except Exception as e:
                    print(f"failed to delete issue comment {e}")

            review_comments = list(pr.get_review_comments())

            if len(review_comments) == 0 and len(comments) == 0:
                # No comments left
                break

            for comment in review_comments:
                # Make sure only touch our bot's comments
                if not comment.user.login.startswith("github-actions"):
                    continue

                try:
                    comment.delete()
                except Exception as e:
                    print(f"failed to delete review comment {e}")

    def number_lines_in_patch(self, changes):
        lines = changes.split("\n")
        out = []
        n = None
        in_hunk = False
        for l in lines:
            if in_hunk and not re.match(r'[ +-]', l):
                in_hunk = False
                n = None
            if in_hunk and not l.startswith("-"):
                n += 1
            if n and l.startswith("-"):
                l = f"\t{l}"
            elif n:
                l = f"{n}\t{l}"
            if l.startswith("@@"):
                in_hunk = True
                m = re.match(r'@@ -\d+,\d+ \+(\d+),\d+ @@', l)
                if not m:
                    raise ValueError(f"Invalid hunk header: {l}")
                n = int(m[1]) - 1
            out.append(l)

        out.append("")

        numbered = "\n".join(out)

        return numbered

    def review_pr(self, payload) -> bool:
        """Review a PR. Returns True if review is successfully generated"""
        pr, changes = self.get_pull_request(payload)

        changes = self.number_lines_in_patch(changes)

        # Delete old comments before adding new ones
        pr_comments_left = self.delete_old_comments(pr)

        # Review the full PR changes together

        prompt = self.llm_client.get_pr_prompt(changes)
        review_json_str, cost = self.get_completion(prompt)
        print(f"review_json={review_json_str}")
        try:
            review_json = json.loads(review_json_str)
            pr_comment = review_json["pr_comment"]
            print(f"pr_comment={pr_comment}")
            file_comments = review_json.get("file_comments", [])
            print(f"file_comments={file_comments}")
        except Exception as e:
            print(f"Exception while generating PR review: {e}\ntraceback.format_exc()")
            return False

        if file_comments and pr_comment == "LGTM":
            pr_comment = "Found some issues"

        # Create comment on whole PR
        pr.create_issue_comment(
            f"{pr_comment}\n\n"
            f"(review was done using={self.llm_client.model} with cost=${cost})"
        )

        files_changed = pr.get_files()
        for file in files_changed:
            for comment in file_comments:
                if file.filename == comment["file"]:
                    try:
                        lines = {
                            "line": comment["line"]
                        }
                        if comment["start_line"] != comment["line"]:
                            lines["start_line"] = comment["start_line"]

                        # Create comment on certain PR line
                        pr.create_review_comment(
                            body=comment["comment"],
                            commit=list(pr.get_commits())[-1],
                            path=file.filename,
                            **lines,
                        )
                    except Exception as e:
                        if (
                            "start_line must be part of the same hunk as the line."
                            in str(e)
                        ):
                            print(f"not using start_line because of issue: {e}")

                            try:
                                pr.create_review_comment(
                                    body="In this file: " + comment["comment"],
                                    commit=list(pr.get_commits())[-1],
                                    path=file.filename,
                                    # Just comment on the same line
                                    # sometimes GPT generates line no
                                    # outside the range of lines in the file
                                    line=1,
                                )
                            except Exception:
                                print("Just skipping the error")

                            continue

                        print(f"failed to comment on file={file.filename}:{line}: {e}")
                        continue

        return True

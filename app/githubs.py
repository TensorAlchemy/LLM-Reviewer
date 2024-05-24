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
        openai_client,
        review_per_file=False,
        comment_per_file=False,
        blocking=False,
    ):
        self.openai_client = openai_client
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_client = Github(self.github_token)
        self.review_tokens = (
            self.openai_client.max_tokens - self.openai_client.min_tokens
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
        if len(self.openai_client.encoder.encode(patch)) < self.review_tokens:
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
            if len(self.openai_client.encoder.encode(line)) < self.review_tokens:
                return line
        return ""

    def get_completion(self, prompt) -> Tuple[str, str]:
        """Get the completion text and cost"""
        try:
            completion_text, cost = self.openai_client.get_completion(prompt)
            return completion_text, cost
        except Exception as e:
            if self.blocking:
                raise e
            else:
                print(
                    f"OpenAI failed on prompt with exception: {e}\n{traceback.format_exc()}"
                )
                return ""

    def review_pr(self, payload) -> bool:
        """Review a PR. Returns True if review is successfully generated"""
        pr, changes = self.get_pull_request(payload)

        # if (
        #     len(self.openai_client.encoder.encode(changes)) < self.review_tokens
        #     and not self.review_per_file
        # ):
        # Review the full PR changes together

        prompt = self.openai_client.get_pr_prompt(changes)
        review_json_str, cost = self.get_completion(prompt)
        print(f"review_json={review_json_str}")
        try:
            review_json = json.loads(review_json_str)
            pr_comment = review_json["pr_comment"]
            print(f"pr_comment={pr_comment}")
            file_comments = review_json["file_comments"]
            print(f"file_comments={pr_comment}")
        except Exception as e:
            print(f"Exception while generating PR review: {e}")
            return False

        # Create comment on whole PR
        pr.create_issue_comment(
            f"{pr_comment}\n\n"
            f"(review was done using={self.openai_client.model} with cost=${cost})"
        )

        files_changed = pr.get_files()
        for file in files_changed:
            for comment in file_comments:
                if file.filename == comment["file"]:
                    try:
                        line = max(1, int(comment["line"]))
                        start_line = max(1, int(comment["start_line"]))
                        start_line = min(start_line, line)

                        # Create comment on certain PR line
                        pr.create_review_comment(
                            body=comment["comment"],
                            commit=list(pr.get_commits())[-1],
                            path=file.filename,
                            line=line,
                            start_line=start_line,
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

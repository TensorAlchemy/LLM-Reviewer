#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import json
import os
import traceback
from typing import Any, List, Optional, Tuple

import numbered_patch
from github import Github
from loguru import logger
from numbered_patch import should_skip_file

# List of event types
EVENT_TYPE_PUSH = "push"
EVENT_TYPE_COMMENT = "comment"
EVENT_TYPE_PULL_REQUEST = "pull_request"
EVENT_TYPE_OTHER = "other"


class GithubClient:
    """Github API client"""

    def __init__(
        self,
        llm_client: Any,
        review_per_file: bool = False,
        comment_per_file: bool = False,
        blocking: bool = False,
        skip_extensions: Optional[List[str]] = None,
    ):
        self.llm_client = llm_client
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_client = Github(self.github_token)
        self.review_tokens = self.llm_client.max_tokens - self.llm_client.min_tokens
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
        """Get the pull request and its changes"""
        try:
            # Get repository from payload
            repo_name = payload["repository"]["full_name"]
            repo = self.github_client.get_repo(repo_name)

            # Get PR number from payload
            pr_number = payload.get("pull_request", {}).get("number")
            if not pr_number:
                raise ValueError("Could not find PR number in payload")

            pr = repo.get_pull(pr_number)

            changes = []
            file_count = 0
            skipped_count = 0

            for file in pr.get_files():
                if should_skip_file(file.filename):
                    skipped_count += 1
                    continue

                logger.debug(
                    f"{file.filename}: {file.status}"
                )  # added, modified, removed
                file_count += 1
                changes.append(f"diff --git a/{file.filename} b/{file.filename}")
                changes.append(f"--- a/{file.filename}")
                changes.append(f"+++ b/{file.filename}")
                if file.patch:
                    changes.append(file.patch)
                changes.append("")  # Empty line between files

            logger.info(f"Processed {file_count} files (skipped {skipped_count})")

            return pr, "\n".join(changes)

        except Exception as e:
            logger.error(f"Error getting pull request details: {e}")
            raise

    def get_completion(self, prompt) -> Tuple[str, float]:
        """Get the completion text and cost"""
        # Check if prompt is too long before sending to LLM
        if self.llm_client.is_text_too_long(prompt):
            logger.error("Prompt exceeds maximum token length")
            return ("", 0.0)
        try:
            completion_text, cost = self.llm_client.get_completion(prompt, json=True)
            return completion_text, cost
        except Exception as e:
            if self.blocking:
                raise e
            else:
                logger.error(
                    f"The LLM failed on prompt with exception: {e}\n"
                    + traceback.format_exc()
                )
                return "", 0.0

    def delete_old_comments(self, pr, attempt: int = 1) -> None:
        """Delete old comments on the PR created by the bot"""

        # Comments API returning paged data,
        # so need to iterate few times to make sure
        # that all comments are deleted
        max_num_of_delete_steps = 16
        for i in range(max_num_of_delete_steps):
            logger.info(f"Deleting old comments [{i}]")
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
                    logger.error(f"failed to delete issue comment {e}")

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
                    logger.error(f"failed to delete review comment {e}")

    def filter_diff(self, changes: str) -> str:
        """Filter a diff to only include relevant file changes.

        Excludes: empty chunks, binary files, and files with skipped extensions.
        """
        if not changes:
            return ""

        filtered_lines = []
        current_file = None

        for line in changes.splitlines():
            # Check for file header lines
            if line.startswith("diff --git"):
                current_file = line.split()[-1][2:]  # Get b/filename part
                if should_skip_file(current_file):
                    logger.debug(f"Skipping {current_file}")
                    current_file = None  # Skip this file
                    continue
                filtered_lines.append(line)

            # Only include lines if we're processing a non-skipped file
            elif current_file is not None:
                filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def _create_comment(self, pr, comment: str, file=None, line=None, start_line=None):
        """Helper to create PR comments with consistent formatting"""
        try:
            if file and line:
                lines = {"line": line}
                if start_line and start_line != line:
                    lines["start_line"] = start_line

                pr.create_review_comment(
                    body=comment, commit=list(pr.get_commits())[-1], path=file, **lines
                )
            else:
                pr.create_issue_comment(
                    f"{comment}\n\n(review was done using={self.llm_client.model})"
                )
        except Exception as e:
            logger.error(f"Failed to create comment: {e}")
            if self.blocking:
                raise

    def review_pr(self, payload) -> bool:
        pr, changes = self.get_pull_request(payload)

        # Filter out irrelevant files first
        filtered_changes = self.filter_diff(changes)

        if not filtered_changes.strip():
            # Create comment for empty/filtered changes
            pr.create_issue_comment(
                f"LGTM (no relevant code changes found)\n\n"
                f"(review was done using={self.llm_client.model})"
            )
            return True

        print(filtered_changes)
        changes = numbered_patch.number_lines_in_patch(filtered_changes)

        # Delete old comments before adding new ones
        self.delete_old_comments(pr)

        # Review the full PR changes together
        prompt = self.llm_client.get_pr_prompt(changes)
        review_json_str, cost = self.get_completion(prompt)
        logger.info(f"review_json={review_json_str}")
        try:
            review_json = json.loads(review_json_str)
            pr_comment = review_json["pr_comment"]
            logger.info(f"pr_comment={pr_comment}")
            file_comments = review_json.get("file_comments", [])
            logger.info(f"file_comments={file_comments}")
        except Exception as e:
            logger.error(
                f"Exception while generating PR review: {e}\n{traceback.format_exc()}"
            )
            return False

        if file_comments and pr_comment == "LGTM":
            pr_comment = "Found some issues"

        # Create comment on whole PR
        self._create_comment(pr, f"{pr_comment} (cost=${cost})")

        files_changed = [f for f in pr.get_files() if not should_skip_file(f.filename)]
        for file in files_changed:
            for comment in file_comments:
                if file.filename == comment["file"]:
                    try:
                        line_no: int = comment["line"]
                        lines = {"line": line_no}

                        if comment["start_line"] != line_no:
                            lines["start_line"] = comment["start_line"]

                        self._create_comment(
                            pr,
                            comment["comment"],
                            file=file.filename,
                            line=line_no,
                            start_line=comment["start_line"],
                        )
                    except Exception as e:
                        if (
                            "start_line must be part of the same hunk as the line."
                            in str(e)
                        ):
                            logger.warning(
                                f"not using start_line because of issue: {e}"
                            )

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
                                logger.warning("Just skipping the error")

                            continue

                        logger.error(
                            f"Failed to comment on file={file.filename}:{line_no}: {e}"
                        )
                        continue

        return True

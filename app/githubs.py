#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import json
import os
import traceback
from typing import Tuple

from loguru import logger

import requests
from github import Github

import numbered_patch

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

    def get_completion(self, prompt) -> Tuple[str, str]:
        """Get the completion text and cost"""
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
                return ""

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

    def review_pr(self, payload) -> bool:
        """Review a PR. Returns True if review is successfully generated"""
        pr, changes = self.get_pull_request(payload)

        changes = numbered_patch.number_lines_in_patch(changes)

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
        pr.create_issue_comment(
            f"{pr_comment}\n\n"
            f"(review was done using={self.llm_client.model} with cost=${cost})"
        )

        files_changed = pr.get_files()
        for file in files_changed:
            for comment in file_comments:
                if file.filename == comment["file"]:
                    try:
                        line_no: int = comment["line"]
                        lines = {"line": line_no}

                        if comment["start_line"] != line_no:
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
                            #
                            "failed to comment on "
                            + f"file={file.filename}:{line_no}: {e}"
                        )
                        continue

        return True

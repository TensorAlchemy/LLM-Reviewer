#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import json
import os
import argparse
import sys

import distutils
import completion
import githubs


# Check required environment variables
if not os.getenv("GITHUB_TOKEN"):
    print("Please set the GITHUB_TOKEN environment variable")
    exit(1)
if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
    print("Please set the OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable")
    exit(1)

# Parse arguments
parser = argparse.ArgumentParser(
    description="Automated pull requests reviewing and issues triaging with an LLM"
)
parser.add_argument("--model", help="LLM model", type=str, default="claude-3-5-sonnet-20240620")
parser.add_argument(
    "--temperature", help="Temperature for the model", type=float, default=0.2
)
parser.add_argument(
    "--frequency-penalty", help="Frequency penalty for the model", type=int, default=0
)
parser.add_argument(
    "--presence-penalty", help="Presence penalty for the model", type=int, default=0
)
parser.add_argument(
    "--review-per-file",
    help="Send out review requests per file",
    type=distutils.util.strtobool,
    default=False,
)
parser.add_argument(
    "--comment-per-file",
    help="Post review comments per file",
    type=distutils.util.strtobool,
    default=True,
)
parser.add_argument(
    "--blocking",
    help="Blocking the pull requests on LLM failures",
    type=distutils.util.strtobool,
    default=False,
)
args = parser.parse_args()


# Initialize clients
llm_client = completion.LLMClient(
    model=args.model,
    temperature=args.temperature,
)
github_client = githubs.GithubClient(
    llm_client=llm_client,
    review_per_file=args.review_per_file,
    comment_per_file=args.comment_per_file,
    blocking=args.blocking,
)


# Load github workflow event
event_file_path = os.environ.get("GITHUB_EVENT_PATH")
if not event_file_path:
    raise FileNotFoundError("Event File Path not found!")

with open(event_file_path, encoding="utf-8") as ev:
    payload = json.load(ev)
eventType = github_client.get_event_type(payload)
print(f"Evaluating {eventType} event")


# Review the changes via an LLM
match eventType:
    case githubs.EVENT_TYPE_PULL_REQUEST:
        if not github_client.review_pr(payload):
            sys.exit(1)
    case _:
        print(f"{eventType} event is not supported yet, skipping")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import os
from typing import Tuple

import backoff
import openai
import tiktoken

from openai import OpenAI

client = OpenAI()

openai.api_key = os.getenv("OPENAI_API_KEY")

system_prompt = """
You are expert Python developer that are reviewing Pull Requests. 
Be compact in your reviews and highlight only important things.
(i.e. potential bugs, security issues and critical parts in code).

Please only submit a comment if the section actually requires the
attention of a senior developer, or if you spot a bug or unused variable etc.

You should not comment on things just because they have changed, you should
comment about logical errors in the codebase or things which could
easily be missed by another senior developer.
"""


class OpenAIClient:
    """OpenAI API client"""

    def __init__(
        self,
        model,
        temperature,
        max_tokens=4000,
        min_tokens=256,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.encoder = tiktoken.encoding_for_model("gpt2")

    @backoff.on_exception(
        backoff.expo,
        (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError),
        max_time=300,
    )
    def get_completion(self, prompt) -> Tuple[str, str]:
        """Invoke OpenAI API to get text completion and cost"""
        completion = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=self.temperature,
        )

        cost = self.calculate_cost(completion.usage)
        content = completion.choices[0].message.content

        return content, cost

    def calculate_cost(self, usage_obj):
        pricing = {
            "gpt-3.5-turbo-1106": {
                "prompt": 0.001,
                "completion": 0.002,
            },
            "gpt-4-1106-preview": {
                "prompt": 0.01,
                "completion": 0.03,
            },
            "gpt-4-0125-preview": {
                "prompt": 0.01,
                "completion": 0.03,
            },
            "gpt-4": {
                "prompt": 0.03,
                "completion": 0.06,
            },
            "gpt-4o": {
                "prompt": 0.005,
                "completion": 0.015,
            },
        }

        try:
            model_pricing = pricing[self.model]
        except KeyError:
            raise ValueError(f"Invalid model {self.model} specified")

        # Workaround when usage_obj is dict
        if isinstance(usage_obj, dict):
            prompt_tokens = usage_obj["prompt_tokens"]
            completion_tokens = usage_obj["completion_tokens"]
        else:
            prompt_tokens = usage_obj.prompt_tokens
            completion_tokens = usage_obj.completion_tokens

        prompt_cost = prompt_tokens * model_pricing["prompt"] / 1000
        completion_cost = completion_tokens * model_pricing["completion"] / 1000
        total_cost = prompt_cost + completion_cost
        # round to 4 decimals
        total_cost = round(total_cost, 4)

        return total_cost

    def get_pr_prompt(self, changes) -> str:
        """Generate a prompt for a PR review to give JSON output with line and comments"""
        prompt = f"""Here are changes for this PR:
```
{changes}
```
Please comment in the JSON standard on the above given git diff.

Produce pure JSON output, without any extra symbols (like ```json etc.),

EXAMPLE:
{{
  "pr_comment": "A short comment on the entire PR (should be compact)",
  "file_comments" : [
      {{
        "file": "path/somefile.py",
        "start_line": 198, <-- Must be <= line
        "line": 200, <-- Should be the exact line you wish to specify
        "comment": "somecomment", <-- Should be compact and helpful
      }},
      ...
  ]
}}
    """
        return prompt

    def get_file_prompt(self, filename, changes) -> str:
        """Generate a prompt for a file review"""
        prompt = f"""Here are changes for file `{filename}` within this PR:
```
{changes}
```
    """
        return prompt


if __name__ == "__main__":
    cli = OpenAIClient(model="gpt-4o", temperature=0.2)
    print(
        cli.get_completion(
            """
    
    
    """
        )
    )

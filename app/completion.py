#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import os
from typing import Tuple
from enum import Enum
from types import SimpleNamespace

import backoff
import openai
import anthropic
import tiktoken

from openai import OpenAI
from anthropic import Anthropic


if os.environ.get("OPENAI_API_KEY"):
    openai_client = OpenAI()
if os.environ.get("ANTHROPIC_API_KEY"):
    anthropic_client = Anthropic()


system_prompt = """
You are expert Python developer reviewing Pull Requests.
Be very concise in your reviews and highlight only important things.
(i.e. potential bugs, security issues and critical parts in code).

Please only submit a comment if the section actually requires the
attention of a senior developer, or if you spot a bug or unused variable etc.

If a change has no bugs or issues, just return the text "LGTM", nothing else.

You should not comment on things just because they have changed, you should
comment about logical errors in the codebase or things which could
easily be missed by another senior developer.

In your review, do not explain any basics that a senior developer would know,
just highight the error without explanation.

YOU MUST NOT MENTION CHECKING CONFIGURATION. Assume a senior developer.

YOU MUST NOT MENTION CHECKING VARIABLE REFERENCES!
"""

class Provider(Enum):
    OPENAI = 1
    ANTHROPIC = 2


class LLMClient:
    """LLM API client"""

    models = {
# commented out obsolete models:
#        "gpt-3.5-turbo-1106": {
#            "input_price": 1,
#            "output_price": 2,
#            "provider": Provider.OPENAI,
#        },
#        "gpt-4-1106-preview": {
#            "input_price": 10,
#            "output_price": 30,
#            "provider": Provider.OPENAI,
#        },
#        "gpt-4-0125-preview": {
#            "input_price": 10,
#            "output_price": 30,
#            "provider": Provider.OPENAI,
#        },
#        "gpt-4": {
#            "input_price": 10,
#            "output_price": 60,
#            "provider": Provider.OPENAI,
#        },
        "gpt-4o": {
            "input_price": 5,
            "output_price": 15,
            "provider": Provider.OPENAI,
        },
        "gpt-4o-mini": {
            "input_price": 0.15,
            "output_price": 0.6,
            "provider": Provider.OPENAI,
        },
        "claude-3-5-sonnet-20240620": {
            "input_price": 3,
            "output_price": 15,
            "provider": Provider.ANTHROPIC,
        },
    }

    exceptions_to_retry = (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError,
         anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError)

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
        try:
            self.model_info = self.models[self.model]
        except KeyError:
            raise ValueError(f"Unknown model {self.model} specified")
        self.provider = self.model_info["provider"]
        if self.provider == Provider.OPENAI:
            self.encoder = tiktoken.encoding_for_model(self.model)
        elif self.provider == Provider.ANTHROPIC:
            self.encoder = None
            pass
        else:
            raise ValueError(f"Unknown provider {self.provider.name}")

    def openai_query(self, prompt) -> Tuple[str, str]:
        response = openai_client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
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
            response_format={ "type": "json_object" }
        )
        content = response.choices[0].message.content
        cost = self.calculate_cost(
            SimpleNamespace(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )
        )
        return content, cost

    def anthropic_query(self, prompt) -> Tuple[str, str]:
        response = anthropic_client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        }
                    ]
                }
            ]
        )
        content = response.content[0].text
        cost = self.calculate_cost(response.usage)
        return content, cost

    @backoff.on_exception(
        backoff.expo,
        exceptions_to_retry,
        max_time=300,
    )
    def get_completion(self, prompt, json=False) -> Tuple[str, str]:
        """Invoke LLM API to get text completion and cost"""

        if self.provider == Provider.OPENAI:
            return self.openai_query(prompt)
        elif self.provider == Provider.ANTHROPIC:
            return self.anthropic_query(prompt)
        else:
            raise ValueError(f"Unknown provider {self.provider.name}")

    def count_tokens(self, text):
        if self.provider == Provider.OPENAI:
            return len(self.encoder.encode(text))
        elif self.provider == provider.ANTHROPIC:
            return len(anthropic_client.count_tokens(text))
        else:
            raise ValueError(f"Unknown provider {self.provider.name}")

    def calculate_cost(self, usage_obj):
        input_tokens = usage_obj.input_tokens
        output_tokens = usage_obj.output_tokens

        input_cost = input_tokens * self.model_info["input_price"] / 1e6
        output_cost = output_tokens * self.model_info["output_price"] / 1e6
        total_cost = input_cost + output_cost
        # round to 4 decimals
        total_cost = round(total_cost, 6)

        return total_cost

    def get_pr_prompt(self, changes) -> str:
        """Generate a prompt for a PR review to give JSON output with line and comments"""
        prompt = f"""Here are changes for this PR:
```
{changes}
```
Please comment in the JSON standard on the above given git diff.

Produce pure JSON output, without any extra symbols (like ```json etc.).

Use the line numbers in the patched code, e.g. for a hunk header:
@@ -46,77 +104,92 @@
use the line numbers starting from 104, not 46.

EXAMPLE:
{
  "pr_comment": "A short comment on the entire PR (should be compact)",
  "file_comments" : [
      {
        "file": "path/somefile.py",
        "start_line": 198, <-- Must be <= line
        "line": 200, <-- Should be the final line
        "comment": "somecomment", <-- Should be compact and helpful
      },
      ...
  ]
}
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
    for model in "gpt-4o-mini", "claude-3-5-sonnet-20240620":
        cli = LLMClient(model=model, temperature=0.2)
        prompt = cli.get_pr_prompt("""
@@ -1,1 +1,1 @@
-print(f"The answer is {42}")
+print("The answer is " + 42)
""")
        content, cost = cli.get_completion(prompt)
        print(model)
        print(content)
        print(cost)

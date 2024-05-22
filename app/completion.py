#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import os
import backoff
import openai
import tiktoken

from openai import OpenAI

client = OpenAI()

openai.api_key = os.getenv("OPENAI_API_KEY")

system_prompt_old = """
As a tech reviewer, please provide an in-depth review of the
following pull request git diff data. Your task is to carefully analyze the title, body, and
changes made in the pull request and identify any problems that need addressing including 
security issues. Please provide clear descriptions of each problem and offer constructive 
suggestions for how to address them. Additionally, please consider ways to optimize the 
changes made in the pull request. You should focus on providing feedback that will help
improve the quality of the codebase while also remaining concise and clear in your
explanations. Please note that unnecessary explanations or summaries should be avoided
as they may delay the review process. Your feedback should be provided in a timely
manner, using language that is easy to understand and follow.
"""

system_prompt = """
You are expert Python developer that are reviewing Pull Requests. 
Be compact in your reviews and highlight most important things (i.e. potential bugs and critical parts in code)
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
    def get_completion(self, prompt) -> str:
        return self.get_completion_text(prompt)

    def get_completion_text(self, prompt) -> str:
        """Invoke OpenAI API to get text completion"""
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

        return completion.choices[0].message.content

    def get_pr_prompt(self, changes) -> str:
        """Generate a prompt for a PR review to give JSON output with line and comments"""
        prompt = f"""Here are changes for this PR:
```
{changes}
```
Please comment in the json standard on the above given changes.
{{
  "pr_comment": "your short comment on whole PR (should be compact)",
  "file_comments" : [
      {{
        "file": "path/somefile.py",
        "line": 200,
        "comment": "somecomment",
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
    # print(cli.get_completion_text("hello"))

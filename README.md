# LLM-Reviewer 

A GitHub Action that automatically reviews pull requests using LLMs (Large Language Models).

## Setup

1. Get an API key from one or more LLM providers:
   - OpenAI: [Get API key](https://platform.openai.com/account/api-keys)  
   - Anthropic: [Get API key](https://console.anthropic.com/settings/keys)

2. Add the API key(s) as [repository secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets#creating-encrypted-secrets-for-a-repository):
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`

3. Create `.github/workflows/llm-review.yml`:

```yaml
name: LLM Review
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: TensorAlchemy/LLM-Reviewer@main
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        with:
          # Optional settings:
          model: "claude-3-5-sonnet-20240620"  # Default model
          temperature: 0.2  # Model randomness (0-1)
          blocking: false   # Block PR on review failures
          review_per_file: false  # Review each file separately
          comment_per_file: true  # Post comments per file
```

## Configuration

### Required Environment Variables

| Name | Description |
|------|-------------|
| GITHUB_TOKEN | GitHub token for posting reviews (auto-provided) |
| OPENAI_API_KEY or ANTHROPIC_API_KEY | At least one LLM provider API key |

### Optional Settings

| Name | Description | Default |
|------|-------------|---------|
| model | LLM model to use | claude-3-5-sonnet-20240620 |
| temperature | Model randomness (0-1) | 0.2 |
| blocking | Block PR if review fails | false |
| review_per_file | Review files separately | false |
| comment_per_file | Post per-file comments | true |
| skip_extensions | File extensions to ignore | png,jpg,etc |

## Notes for Repository Forks

For security, GitHub runs workflows from forked repository PRs with read-only permissions and no access to secrets.

To enable reviews on fork PRs, use `pull_request_target` instead of `pull_request` in your workflow. This runs the workflow in the base repository's context. [Learn more](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#pull_request_target).

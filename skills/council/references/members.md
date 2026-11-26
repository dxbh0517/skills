# Default council

Edit this table to change who sits on the council. Pick members from
different model families so their blind spots differ.

| Delegate | Harness | Model | Cost tier |
| --- | --- | --- | --- |
| Claude Opus 5.5 | Claude Code | `claude-opus-5-5` | expensive |
| Grok 4.7 | Cursor | `grok-4.7-high` | mid |
| OpenRouter Free | OpenCode | `openrouter/openrouter/free` (any `:free` model) | free |
| vLLM Auto (local) | OpenCode | `vllm-router/auto` | local |

## Notes

- **Local vLLM member:** runs through a local OpenAI-compatible router
  (for example `http://127.0.0.1:8899/v1`). Start the router if it is not
  running; if it still fails, mark the member `skipped (unavailable)`.
- **OpenRouter free models** are rate limited. If one fails, retry once with
  another `:free` model and note the swap in the report.
- **Frugal mode:** members marked `expensive` sit in round 1 and the final
  confirmation round only.
- **Design or visual reviews:** give every member the same screenshots (mobile
  and desktop) along with the code; members that cannot see images review the
  code and say so.

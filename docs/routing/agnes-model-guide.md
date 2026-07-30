# Agnes model guide

Agnes is now wired into the shared router as a first-class cloud provider and defaults to the text-first model `agnes-2.5-flash`.

## Recommended model choices

| Workload | Recommended model | Why |
| --- | --- | --- |
| General chat, summaries, planning, and lightweight coding help | `agnes-2.5-flash` | Best default for fast, capable text work. |
| Multi-step reasoning, structured planning, and policy-heavy tasks | `agnes-2.5-flash` | Use as the default unless a task clearly needs a specialized non-Agnes provider. |
| Image generation | `agnes-image-2.0-flash` | Best fit for fast image creation and iteration. |
| Higher-fidelity image generation | `agnes-image-2.1-flash` | Prefer when image quality matters more than latency. |
| Video generation | `agnes-video-v2.0` | Use for video creation workflows rather than standard chat or coding tasks. |

## Routing guidance

- Keep `agnes-2.5-flash` as the default provider for planning and general agent-style tasks in the shared router.
- Reserve image and video models for multimodal workflows rather than ordinary text tasks.
- If the task is latency-sensitive and the workspace is offline or on battery, the router will still force low mode and prefer local/low-cost options.

## Notes

- The router’s default preference is set in [09_DEPLOYMENT/config/routing/user-preferences.yaml](../09_DEPLOYMENT/config/routing/user-preferences.yaml).
- The provider inventory and default model live in [config/routing/providers.yaml](../config/routing/providers.yaml).

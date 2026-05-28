# Provider Matrix

| Provider | Type | Status | Adapter Path | Env Key | Notes |
|---|---|---|---|---|---|
| Ollama | local | ✅ Ready | `adapters/ollama_adapter.py` | — | Requires local Ollama server |
| LM Studio | local | 🚧 Stub | `adapters/lmstudio_adapter.py` | — | OpenAI-compatible local server |
| OpenAI | frontier | 🚧 Stub | `adapters/openai_adapter.py` | `OPENAI_API_KEY` | GPT-4o, GPT-4o-mini |
| Anthropic | frontier | 🚧 Stub | `adapters/anthropic_adapter.py` | `ANTHROPIC_API_KEY` | Claude Sonnet, Opus |
| Google | frontier | 🚧 Stub | `adapters/google_adapter.py` | `GOOGLE_API_KEY` | Gemini 2.5 Flash/Pro |
| OpenRouter | broker | 🚧 Stub | `adapters/openrouter_adapter.py` | `OPENROUTER_API_KEY` | Unified API |
| Featherless | broker | 🚧 Stub | `adapters/featherless_adapter.py` | `FEATHERLESS_API_KEY` | Free/open models |
| OpenHuman | sidecar | ✅ Ready | `adapters/openhuman_adapter.py` | `OPENHUMAN_BEARER_TOKEN` | Disabled by default |

Legend:
- ✅ Ready = adapter implements health + complete
- 🚧 Stub = adapter skeleton exists, needs SDK wiring

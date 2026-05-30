# Agent Router Graph

```mermaid
flowchart LR
    Intent[User Intent / Queue Item] --> Classifier[Task Classifier]
    Classifier --> Planner[Planner]
    Classifier --> Builder[Builder]
    Classifier --> Auditor[Auditor]
    Classifier --> Scout[Scout]
    Classifier --> Scribe[Scribe]
    Classifier --> Incident[Incident Handler]

    Planner --> Claude[Claude: synthesis / planning]
    Builder --> Codex[Codex / Code Agent: repo edits]
    Auditor --> GPT[ChatGPT: review / orchestration]
    Scout --> Gemini[Gemini: broad or multimodal context]
    Scribe --> Local[Local LLM: cheap routine updates]
    Incident --> Human[Human Gate]

    Claude --> Evidence[Evidence Pack]
    Codex --> Patch[Scoped Patch]
    GPT --> Review[Review Result]
    Gemini --> Context[Context Summary]
    Local --> State[State Update]

    Evidence --> Gate[Confidence Gate]
    Patch --> Gate
    Review --> Gate
    Context --> Gate
    State --> Gate
```

## Routing notes

Use specialization, not popularity:

- Claude: long synthesis, careful docs, strategy.
- ChatGPT: orchestration, structured review, tool-aware planning.
- Codex/code agents: patches, tests, refactors.
- Gemini: broad context and multimodal comparison.
- Local models: cheap classification, summarization, queue triage.

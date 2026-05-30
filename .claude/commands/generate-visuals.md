# Claude Command: Generate Visuals

Run the visual-control sequence:

1. Read `visual_node_registry.json`.
2. Validate node and edge integrity.
3. Run `python scripts/validate_visual_registry.py`.
4. Run `python scripts/generate_harness_mermaid.py`.
5. Summarize changed files and any validation concerns.

Stop if registry validation fails.

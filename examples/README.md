# Examples

The two Markdown files under `inputs/` are **synthetic sample architecture documents** included only
to demonstrate the input format and the end-to-end flow. Replace them with your own architecture
documents when using the agent for a real project.

| Path | Purpose |
|---|---|
| `inputs/Architecture_Documentation.md` | Sample architecture document used by the demo |
| `inputs/Architecture_View.md` | Sample PlantUML views (13 blocks, 11 view types) |
| `report-sample/GENERATION_REPORT.md` | Sanitized report produced by a Mock run (100% coverage) |
| `report-sample/traceability_matrix.csv` | Requirement → source/test matrix from the same run |

## Run the demo

From the repository root:

```powershell
python -m space_code_agent --mock-run .\out\demo `
  --doc .\examples\inputs\Architecture_Documentation.md `
  --uml .\examples\inputs\Architecture_View.md --allow-tests
```

The output project is a runnable Space Fractions demo (Node.js ≥ 20, zero runtime dependencies).

> The sample report's local absolute paths were replaced with relative paths before publication;
> the session identifier is shown as `<session>`. No API key or machine identifier is present.

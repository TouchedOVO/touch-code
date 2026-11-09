# T15 — Clean Windows runner without Python/Qt

**Run:** [T15 clean Windows runner #1](https://github.com/TouchedOVO/touch-code/actions/runs/42643238074)  
**Result:** **PASS**  
**Runner:** GitHub-hosted `windows-latest` (fresh ephemeral Windows VM)  
**Commit:** `7e9f17e`

## What was done

1. Built the one-file `SpaceCodeAgent.exe` on the runner.
2. **Removed Python before running the EXE**:
   - the runner's Python tool cache and `Program Files\Python*`
   - the project `.venv`
   - `python.exe` / `py.exe` launchers
   - reset `PATH` to `System32`, `Windows` and the Node 22 directory.
3. Verified `Get-Command python` and `Get-Command pip` both fail, and no `Python*`
   directory remains under `Program Files`.
4. Ran the EXE:
   - `--smoke-test` (headless Qt) → exit code **0**
   - GUI process launch → still alive after 6 s
   - full `--mock-run … --allow-tests` with the two sample architecture documents
5. Verified the result:
   - Agent status `completed`
   - file mapping **100%**, test verification **100%**
   - generated Node tests passed
   - Node 22.23.4 remains available for the generated project (allowed; the target
     requirement is no Python/Qt, not no Node)

## Evidence

| File | Content |
|---|---|
| `t15-result.json` | `python_available: false`, EXE hash, status, coverage, tests |
| `agent-result.json` | Full CLI result |
| `run_manifest.json` | Generated run manifest |
| `GENERATION_REPORT.md` | Generated project report |
| `traceability_matrix.csv` | Requirement traceability |

EXE SHA-256: `A5E23A34D25197017056002930457FC7E27707A9A846C0DE3D82E0C3DB92C561`

## Limitation

This is an automated **fresh GitHub Windows runner**, with Python/Qt removed before the EXE
execution. It is not a manually clicked desktop VM, so a final manual double-click test on a
completely clean Windows Pro/Enterprise VM remains a nice-to-have but is no longer an unverified
dependency: the EXE ran without any Python or Qt installation.

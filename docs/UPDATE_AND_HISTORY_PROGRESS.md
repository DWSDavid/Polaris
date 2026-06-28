# Polaris Update and History Progress

## 2026-06-29 MacBook migration checkpoint

Purpose: make the active Polaris implementation movable to the MacBook through GitHub, while keeping account parameters and local market data out of git.

Current source checkout:

- Windows path: `D:\Polaris`
- GitHub repo: `https://github.com/DWSDavid/Polaris.git`
- Active branch: `codex/polaris-implementation-tasks-1-11`
- Remote tracking branch: `origin/codex/polaris-implementation-tasks-1-11`
- Local status at checkpoint: branch is aligned with origin, no unpushed commits
- Local untracked item intentionally not included in migration commit: `artifacts/` screenshot outputs

MacBook restore path:

```bash
git clone -b codex/polaris-implementation-tasks-1-11 https://github.com/DWSDavid/Polaris.git
cd Polaris
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run src/app/Home.py
```

Hand-carry or recreate on the MacBook:

- `.env` with API tokens and model/provider settings
- `data/account/` with local margin-account parameters
- `data/cache/` only if you want to preserve downloaded market cache; otherwise it can be regenerated

Do not commit these files or directories. They are intentionally gitignored.

Ongoing development rule:

1. Work on a branch and push it to GitHub.
2. Keep account data, tokens, logs, caches, and local screenshots out of source unless a screenshot is intentionally promoted into docs.
3. Run the relevant pytest/Streamlit smoke checks before pushing implementation changes.
4. Update this file after meaningful milestones, migrations, deploy changes, data-provider changes, account-model changes, or rollback decisions.


# Team Report

## 1. Metrics

Metrics were computed from the frontend project in `../frontend` and the backend project in `../backend`.

Scope notes:
- LOC counts non-empty source lines only.
- Generated output, build artifacts, cache folders, and VCS metadata are excluded.
- Cyclomatic complexity is based on supported source files analyzed with `lizard`.
- Dependency count is the number of direct dependencies declared in manifests, not transitive dependencies from lockfiles.

| Project | Source files | LOC | Functions | Total CCN | Avg CCN/function | Max CCN | Direct deps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| frontend | 97 | 16,168 | 608 | 1,655 | 2.72 | 41 | 48 |
| backend | 135 | 19,146 | 1,239 | 3,316 | 2.68 | 45 | 26 |
| total | 232 | 35,314 | 1,847 | 4,971 | 2.69 | 45 | 74 |

Highest-complexity functions observed:
- `backend`: `run._run(job: _ConversationJobState)` in `src/agent/api/conversation_runner.py` with CCN 45
- `frontend`: `cronToHuman(cron: null)` in `src/utils/tasks.ts` with CCN 41

## 2. CI/CD Pipeline Description

The project uses GitHub Actions for CI/CD across the repository root, `../frontend`, and `../backend`.

Pipeline steps:
1. Checkout repository sources.
2. Set up runtime tools.
3. Install dependencies.
4. Run tests, builds, metrics, or packaging jobs.
5. Deploy artifacts or publish run summaries.

Implemented workflows and tools:
- Code metrics pipeline: [`.github/workflows/code-metrics.yml`](./.github/workflows/code-metrics.yml)
  - Uses `actions/checkout`, `actions/setup-python`, `pip`, and the repository script [`.github/scripts/code_metrics.py`](./.github/scripts/code_metrics.py).
  - Installs `lizard` and `tomli`, then generates `summary.md` and `code-metrics.json`, and uploads them as an artifact.
- Desktop release pipeline: [`.github/workflows/tauri-release.yml`](./.github/workflows/tauri-release.yml)
  - Uses `actions/checkout`, `actions/setup-node`, `dtolnay/rust-toolchain`, `swatinem/rust-cache`, `npm ci`, and `npx tauri build`.
  - Downloads the bundled CPython runtime, installs the backend package into it, stages it for Tauri, and builds release bundles for Windows, Linux, and macOS.
- Frontend deployment pipeline: [`../frontend/.github/workflows/deploy.yml`](../frontend/.github/workflows/deploy.yml)
  - Uses `actions/checkout`, `npm ci`, `npm run build`, and a self-hosted runner.
  - Builds the frontend and copies the `dist` output to `/var/www/opencrab` for Nginx serving.
- Backend CI/CD pipeline: [`../backend/.github/workflows/deploy.yml`](../backend/.github/workflows/deploy.yml)
  - Uses `actions/checkout`, `actions/setup-python`, `pip`, `pytest`, and `docker build`.
  - Runs backend tests on pull requests and pushes, builds a Docker image, and deploys the container on a self-hosted runner for the `backend-new` branch.

Pipeline configuration access:
- [Root code metrics workflow](./.github/workflows/code-metrics.yml)
- [Root Tauri release workflow](./.github/workflows/tauri-release.yml)
- [Frontend deploy workflow](../frontend/.github/workflows/deploy.yml)
- [Backend deploy workflow](../backend/.github/workflows/deploy.yml)
- [Metrics script](./.github/scripts/code_metrics.py)

Pipeline execution proof:

https://github.com/sustech-cs304/team-project-26spring-26s-1/actions
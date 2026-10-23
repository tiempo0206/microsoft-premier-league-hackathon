# Role B backend

Start with the [single backend handoff](../docs/handoff/backend.md): current public service, API contract, data, credentials required by the release Agent, commands and remaining integration work.

| Modules | Purpose |
| --- | --- |
| app / http / settings | API, bounded input/error handling and runtime configuration |
| data / audit / stats / inputs | Validated synthetic data, deterministic metrics and AnalysisRequest |
| replays / analysis | Isolated replay, SSE and bounded async AI handoff |
| reporting / showcase / backtest | Reproducible reports, inputs and regression |
| run | Backend-only container entry; no model injection |

Detailed metric definitions and generated artifacts: [DATA_PIPELINE.md](DATA_PIPELINE.md).
Docker and release utilities: [deploy/README.md](../deploy/README.md).

Contract2.0.0 and frozen source fixtures are unchanged. Backend preview is API-only; the handoff contains the final integrator's composition and deployment steps.

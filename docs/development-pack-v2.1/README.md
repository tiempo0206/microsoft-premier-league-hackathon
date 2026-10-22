# Three-person development starter v2.1

This internal team pack provides readable Markdown plans and a frozen development baseline for three teammates using different coding AIs. Development favors mainland-accessible resources; the final website may use an international container host.

## Start here

- [Overall plan (Chinese)](package/00_总方案.md)
- [Role-by-role development and AI instructions (Chinese)](package/01_三人开发与AI指令.md)
- [Mainland development and international deployment (Chinese)](package/02_国内开发与国际部署.md)
- [Download the complete development pack](MatchMind_AI_v2.1_CN_dev.zip)
- [Starter entry point](package/starter-overlay/matchmind/START_HERE.md)

## Three roles

| Role | Responsibility | Independent starting point |
| --- | --- | --- |
| A | Frontend, replay interaction, evidence views and audience modes | Local mock API and frozen TypeScript types |
| B | Data, statistics, replay sessions, API, SSE and deployment | Included synthetic fixture and offline AI stub |
| C | Model access, agents, evidence checking, evaluation and integration | Fixed analysis input and shared contracts |

No individual assignment is forced by this upload. The current user's proposed backend role can be confirmed in the team kickoff.

## Integration boundary

This directory is reference material. The starter is **not** installed at repository root and does not replace existing application work. The designated integrator should review the pack and add the `matchmind` overlay to the agreed application path once the team accepts the baseline. Preserve existing code and follow the repository's contribution process.

Package release: **2.1**. Runtime contract: **2.0.0**. Source checks and resource guidance were prepared on October 21, 2026; this repository delivery was prepared on October 22, 2026 (Asia/Shanghai).

The included verification notes describe the original starter checks. A running frontend, production backend, live model workflow, cloud resources and competition submission still require implementation. No real keys, user documents, dependency directories or caches are included.

Related task: [#4](https://github.com/tiempo0206/microsoft-premier-league-hackathon/issues/4).

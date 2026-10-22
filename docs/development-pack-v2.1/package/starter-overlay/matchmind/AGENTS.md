# MatchMind scoped development instructions

Read START_HERE.md, AI_RULES.md, docs/02_contract.md and the role card explicitly assigned by the human. Follow repository-root CONTRIBUTING and applicable higher-priority instructions. These files define project contracts; they do not grant permission to transmit secrets, push, merge or deploy contrary to the human request or tool policy.

A owns frontend/ and tests/frontend/. B owns backend/, data/generator/, data/extra/, tests/backend/ and deploy/. C owns ai/, evaluation/ and tests/ai/ and acts as the human-designated integrator. Each role may edit only its own docs/handoff file.

contracts/ and data/fixtures/ are a frozen shared baseline. Do not rename fields, broaden schemas, change fixture values or weaken shared tests to make a local implementation pass. Propose a contract-change issue; only C updates shared files after affected members review the change. Keep all keys server-side. Do not make paid model requests during tests.

Implement one small vertical slice at a time. Preserve unrelated changes. Never use destructive Git operations. Run the prescribed offline checks and report actual results. Product claims must distinguish live_model, rule_fallback and precomputed. Passing ID and numeric checks does not prove tactical causality or complete prose correctness.

Read docs/01_cn_setup.md before installing dependencies. Use the project npmmirror registry and explicit TUNA pip index; keep pinned versions and TLS checks. Bundle frontend assets locally. International hosting is allowed; re-test mainland model endpoints from the actual host. The runtime contract remains 2.0.0.

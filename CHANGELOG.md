# [1.7.0](https://github.com/kheuchi/rag-platform-app/compare/v1.6.3...v1.7.0) (2026-04-14)


### Features

* align RCA observability stack with otel demo ([#7](https://github.com/kheuchi/rag-platform-app/issues/7)) ([b4eabcd](https://github.com/kheuchi/rag-platform-app/commit/b4eabcd06a7bd6864d308a49c3718b545a398394))

## [1.6.3](https://github.com/kheuchi/rag-platform-app/compare/v1.6.2...v1.6.3) (2026-04-13)


### Bug Fixes

* upgrade base image packages before release scan ([#3](https://github.com/kheuchi/rag-platform-app/issues/3)) ([db52b0a](https://github.com/kheuchi/rag-platform-app/commit/db52b0ac2fcd97ff7e1d3c0f76bb00bf6dc9e526))

## [1.6.2](https://github.com/kheuchi/rag-platform-app/compare/v1.6.1...v1.6.2) (2026-04-13)


### Bug Fixes

* prevent rca probe stalls and skip unknown service chunks ([#2](https://github.com/kheuchi/rag-platform-app/issues/2)) ([056cdb2](https://github.com/kheuchi/rag-platform-app/commit/056cdb2eb2b7765ffd2ab98c7a88e57bac66bc9e))

## [1.6.1](https://github.com/kheuchi/rag-platform-app/compare/v1.6.0...v1.6.1) (2026-04-13)


### Bug Fixes

* **worker:** map renamed OTel demo service paths ([#1](https://github.com/kheuchi/rag-platform-app/issues/1)) ([cfe274f](https://github.com/kheuchi/rag-platform-app/commit/cfe274f8c439ef012c90a5f90b4222d1955e6911)), closes [#9](https://github.com/kheuchi/rag-platform-app/issues/9)

# [1.6.0](https://github.com/kheuchi/rag-platform-app/compare/v1.5.1...v1.6.0) (2026-04-11)


### Features

* stabilize smoke test and document architecture ([a8faaa1](https://github.com/kheuchi/rag-platform-app/commit/a8faaa17dc2aaa2fa77d270a56baa1a90c2b6b90))

## [1.5.1](https://github.com/kheuchi/rag-platform-app/compare/v1.5.0...v1.5.1) (2026-04-08)


### Bug Fixes

* trivyignore unfixed Debian CVEs (ncurses CVE-2025-69720, systemd CVE-2026-29111) ([ddc2054](https://github.com/kheuchi/rag-platform-app/commit/ddc2054904f8ac0b6b27c9a7d747b636ea25cc52))

# [1.5.0](https://github.com/kheuchi/rag-platform-app/compare/v1.4.0...v1.5.0) (2026-04-08)


### Features

* Phase 4.6 + 5 — Vertex AI fallback, Langfuse tracing, smoke test RCA step ([b9910ae](https://github.com/kheuchi/rag-platform-app/commit/b9910aee0deb08bed87fb85b60d9448087e80203))

# [1.4.0](https://github.com/kheuchi/rag-platform-app/compare/v1.3.5...v1.4.0) (2026-03-29)


### Features

* Phase 4.5d — add e2e smoke test script ([6d44adf](https://github.com/kheuchi/rag-platform-app/commit/6d44adfdc4121d8542c7ef3781fe845999637183))

## [1.3.5](https://github.com/kheuchi/rag-platform-app/compare/v1.3.4...v1.3.5) (2026-03-29)


### Bug Fixes

* trivyignore unfixed Debian CVEs (gnupg CVE-2026-24882, libexpat CVE-2026-25210) ([063d0f4](https://github.com/kheuchi/rag-platform-app/commit/063d0f40e54c4e1bb9445c3fbee55983c1148e10))

## [1.3.4](https://github.com/kheuchi/rag-platform-app/compare/v1.3.3...v1.3.4) (2026-03-29)


### Bug Fixes

* bump pydantic>=2.11.5, free more disk + scanners=vuln for Trivy ([297cf4e](https://github.com/kheuchi/rag-platform-app/commit/297cf4e084cebd3433db00775a2cc8268da52e4c))

## [1.3.3](https://github.com/kheuchi/rag-platform-app/compare/v1.3.2...v1.3.3) (2026-03-29)


### Bug Fixes

* pin llama-index-core==0.14.18 to stop pip backtrack, free disk for Trivy ([856b3cb](https://github.com/kheuchi/rag-platform-app/commit/856b3cbd02af1a28fd9de9c9d10d4e081eb191e0))

## [1.3.2](https://github.com/kheuchi/rag-platform-app/compare/v1.3.1...v1.3.2) (2026-03-29)


### Bug Fixes

* langchain-core>=1.1,<2 — v2.0 does not exist on PyPI yet ([2c646f8](https://github.com/kheuchi/rag-platform-app/commit/2c646f88ae19ae1c2a945f7ea98fa545740e4866))

## [1.3.1](https://github.com/kheuchi/rag-platform-app/compare/v1.3.0...v1.3.1) (2026-03-29)


### Bug Fixes

* pin langchain-core>=2.0 to match langchain-openai>=1.1 requirement ([b28543a](https://github.com/kheuchi/rag-platform-app/commit/b28543a5bf363ba4746069eded1ac365b4b35f2e))

# [1.3.0](https://github.com/kheuchi/rag-platform-app/compare/v1.2.0...v1.3.0) (2026-03-29)


### Bug Fixes

* CI docker builds — libgl1-mesa-glx → libgl1, pin langsmith to avoid pip backtrack ([8f0ea76](https://github.com/kheuchi/rag-platform-app/commit/8f0ea76dcb0cbe8727afb14a09cfd8e1f82bdb52))


### Features

* Phase 4.5c — swap Azure AI Search → GCP Firestore vector store [skip ci] ([a2529f9](https://github.com/kheuchi/rag-platform-app/commit/a2529f949151b4694c179d7f66175e8eeb7e6ad3))

# [1.2.0](https://github.com/kheuchi/rag-platform-app/compare/v1.1.5...v1.2.0) (2026-03-29)


### Features

* Phase 4.1 — restructure backend and worker into modular packages [skip ci] ([8f55f0f](https://github.com/kheuchi/rag-platform-app/commit/8f55f0f3c732de81fddbb37627ffb8fb1287fba5))
* Phase 4.2 — implement cold path ingestion pipeline [skip ci] ([8051c3a](https://github.com/kheuchi/rag-platform-app/commit/8051c3ac9f6242b32b9fff47aa8e87069df837f9))
* Phase 4.3 — implement hot path observability tools [skip ci] ([392da25](https://github.com/kheuchi/rag-platform-app/commit/392da25d6fe3e385aa08aa8094bb4ee67cb2267d))
* Phase 4.4 — implement LangGraph RCA agent with SSE streaming [skip ci] ([2084e06](https://github.com/kheuchi/rag-platform-app/commit/2084e06cd02ba45f9b80f95f4e26d806cf14b253))

## [1.1.5](https://github.com/kheuchi/rag-platform-app/compare/v1.1.4...v1.1.5) (2026-03-17)


### Bug Fixes

* **ci:** trigger CI on push to main for CodeQL dashboard ([1b752a2](https://github.com/kheuchi/rag-platform-app/commit/1b752a2a6e37bbad6aee5b31156ebbb87e9dadde))

## [1.1.4](https://github.com/kheuchi/rag-platform-app/compare/v1.1.3...v1.1.4) (2026-03-17)


### Bug Fixes

* **backend:** bump redis to 7.3.0 and drop explicit PyJWT pin ([e518efa](https://github.com/kheuchi/rag-platform-app/commit/e518efa6c0dee61c57caef2a1991ef5ac1337504))

## [1.1.3](https://github.com/kheuchi/rag-platform-app/compare/v1.1.2...v1.1.3) (2026-03-17)


### Bug Fixes

* **backend:** bump fastapi to 0.135.1 and pin PyJWT>=2.12.0 ([b4097f8](https://github.com/kheuchi/rag-platform-app/commit/b4097f89ae3fb21f4ad1dab31a1a5e9e19c953bb))

## [1.1.2](https://github.com/kheuchi/rag-platform-app/compare/v1.1.1...v1.1.2) (2026-03-17)


### Bug Fixes

* **ci:** bump trivy-action from 0.28.0 to 0.35.0 ([5323f07](https://github.com/kheuchi/rag-platform-app/commit/5323f077e90eacf958a7650348e2fe988708ed8c))

## [1.1.1](https://github.com/kheuchi/rag-platform-app/compare/v1.1.0...v1.1.1) (2026-03-17)


### Bug Fixes

* **ci:** use build-push-action digest output for Cosign signing and SBOM ([884ab42](https://github.com/kheuchi/rag-platform-app/commit/884ab42206e5d5b286391b7ab029e800f0131204))

# [1.1.0](https://github.com/kheuchi/rag-platform-app/compare/v1.0.1...v1.1.0) (2026-03-17)


### Features

* **ci:** add supply chain security — CodeQL, Trivy gate, Cosign signing & SBOM attestation ([876aa6d](https://github.com/kheuchi/rag-platform-app/commit/876aa6d80dd33a921fc677095da988ec2bdb0ebc))

## [1.0.1](https://github.com/kheuchi/rag-platform-app/compare/v1.0.0...v1.0.1) (2026-03-16)


### Bug Fixes

* **ci:** use cycjimmy/semantic-release-action for job outputs ([5131aa9](https://github.com/kheuchi/rag-platform-app/commit/5131aa99464dcb01d5c12c1d12ac62588b333a02))

# 1.0.0 (2026-03-16)


### Features

* scaffold RAG backend and worker with CI/CD pipeline ([0c81414](https://github.com/kheuchi/rag-platform-app/commit/0c81414c34be3aa31ee71f31a7bbb845602d1710))

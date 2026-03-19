---
name: CI/CD and Security Preferences
description: User preferences on CI/CD tooling, supply chain security choices, and what NOT to add
type: feedback
---

No Dependabot/Renovate — user explicitly excluded automated dependency PRs.
**Why:** User prefers manual control over dependency updates.
**How to apply:** Never suggest adding Dependabot or Renovate.

No SLSA provenance — user explicitly excluded.
**Why:** Considered overkill for this project scope.
**How to apply:** Don't add SLSA provenance steps to CI.

Trivy runs locally on the runner, does NOT send code externally — user asked about this, confirmed it's secure.
**Why:** User is security-conscious about code leaking to third parties.
**How to apply:** When suggesting security tools, clarify if they run locally vs SaaS.

Trivy reports only in workflow logs — user noted this. Could be improved with SARIF upload to GitHub Security tab (one-line change) but not requested yet.

User pushes directly to main (no PRs for this repo). CodeQL needs push trigger on main to actually run.

Pre-built CI images (with cosign/trivy pre-installed): user asked about this. Advised against it — install steps are fast (1s for cosign), and maintaining a custom CI image adds complexity. User accepted this.

Semantic-release uses cycjimmy/semantic-release-action@v4 (NOT npx).

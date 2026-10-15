# Maintainer checklist

## Review and repository hygiene

- Keep `main` buildable; review focused PRs and require evidence for compatibility claims.
- Run `python tools/run_checks.py`. Native runtime changes additionally need a Windows
  build and appropriate local game tests; GitHub CI has no disc or generated game data.
- Retain upstream credit, third-party license notices and authorship. Do not rewrite
  history simply to remove attribution or hide regressions.
- Keep game data, private logs, caches, saves and generated output out of commits
  and Actions artifacts. Use synthetic examples in CI.
- Use `bug`, `enhancement`, `documentation`, `question` and `accessibility` labels
  for triage. Apply `good first issue` only after a task is understood and bounded.
- Update compatibility evidence and the Unreleased changelog as changes land.
- Delete merged feature branches. Do not delete active local checkouts or their saves.
- Give credit when closing an issue and explain scope decisions respectfully.

## Branch protection and security

GitHub currently reports that branch protection requires upgrading the account
or making this private repository public. Visibility remains private. No branch
protection rule is claimed to be active. If the plan changes, protect `main`
against force pushes/deletion and require the CI check before merging; review
requirements should fit the actual number of available maintainers.

Actions use read-only repository permissions and pinned action revisions.
Dependabot proposes updates to those action references. Do not execute untrusted
PR code with write tokens or secrets, and do not use `pull_request_target` to
run contributed code. This project has no automated game-data upload workflow.
Use the [security reporting process](../SECURITY.md); reassess private vulnerability
reporting if the repository becomes public. Never change visibility just to pass a checklist.

## Releases

1. Finish review and Windows/game tests. Record the exact coverage and limitations.
2. Update the version consistently in installer UI, manifest, build script, player
   instructions and release notes. Commit before making the final package.
3. Follow the [installer guide](../packaging/ac4/installer/README.md). Test importing
   the supported ISO and rejection/cancellation paths in a fresh scratch directory.
4. Inspect the payload manifest: runtime, required DLLs/shaders, clean defaults
   and licenses only. No ISO, memory image, assets, saves or development logs.
5. Verify the embedded payload and installer checksum. Tag the tested commit.
6. Upload to a draft release; check asset sizes/digests and notes before publishing.
   Keep the beta/prerelease flag until broader campaign evidence justifies changing it.
7. Publish new versions for changed binaries. Never silently overwrite an existing
   version's installer; label a withdrawn build and explain the replacement.

Keep the release notes, README and compatibility checklist honest about unsigned
installers, optional HD art, test coverage and known limitations. The GitHub
community checklist measures repository setup, not game correctness or safety.

# Contributing

## Access

The owner invites teammates through GitHub **Settings → Collaborators**. Accept your invitation before cloning. Use individual GitHub accounts and keep credentials local.

## Development workflow

1. Create an Issue describing the task and its acceptance criteria. Claim it before starting.
2. Start a branch from the current `main`:

   ```sh
   git switch main
   git pull --ff-only origin main
   git switch -c feat/short-description
   ```

   Use `fix/` or `docs/` when appropriate. Keep each branch focused on one task.

3. Implement the change and run the relevant checks. Once the stack is chosen, document the shared setup and check commands in the README.
4. Review and commit the intended files, then push your branch:

   ```sh
   git status --short
   git add path/to/changed-file
   git diff --cached
   git commit -m "Describe the change"
   git push -u origin HEAD
   ```

5. Open a pull request against `main`, link the Issue, describe validation, and request a teammate's review.
6. After review, squash and merge the pull request. Update your local `main` before starting the next task.

## Working agreements

- Keep code identifiers and submission-facing documentation in English; add English translations when needed.
- Put secrets in ignored local configuration or the deployment platform's secret store. Commit only placeholder configuration examples.
- Use data and assets the team is authorized to use; record third-party sources and licenses when introducing them.
- Follow the [code of conduct](CODE_OF_CONDUCT.md) and consult the [official hackathon sources](docs/hackathon.md).

The review workflow above is a team convention; repository branch protection is not configured.

# Security Policy

## Supported versions

Alfred is pre-release software and has no supported release line yet. Security fixes land on the
`master` branch; always test against the latest `master` before reporting.

## Reporting a vulnerability

Report suspected vulnerabilities privately through GitHub's private vulnerability reporting:

<https://github.com/madhavan347/project_alfred/security/advisories/new>

Do not open a public issue, discussion, or pull request for a suspected vulnerability, and do not
include secrets, private prompts, task content, or repository paths in any public channel.

A useful report includes:

- the affected revision (commit SHA) and macOS, Python, Git, and tmux versions;
- the impact: what an attacker can read, change, or run, and what access they need first;
- a minimal reproduction using a disposable workspace and repository;
- any suggested mitigation.

The owner will acknowledge the report, assess it, prepare a fix, and coordinate disclosure with you
before details are made public. Please allow time for a fix before disclosing it yourself.

## Security boundaries

Alfred coordinates local command-line tools and Git repositories. Users remain responsible for the
permissions and behavior of configured agent executables, repository remotes, tmux sessions, and
files exposed through prompts. Review `.alfred/config.toml` and generated prompt/completion content
before use in a sensitive workspace.

A workspace configuration chooses the commands Alfred runs, so opening an untrusted
`.alfred/config.toml` is equivalent to running its code. Reports that depend only on an attacker
already controlling the configuration are out of scope unless they bypass a documented safety
invariant, such as explicit-only push or forced dirty-worktree cleanup.

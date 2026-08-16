# Security Policy

Alfred is pre-release software and currently has no supported release line.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or include secrets, private prompts, task
content, repository paths, or exploit details in public discussion. After the repository is
published, use its private GitHub security-advisory reporting channel.

Until private reporting is configured, authorized collaborators should contact the repository owner
through an already established private channel. Include the affected version or revision, impact,
minimal reproduction, and any suggested mitigation. The owner will acknowledge, assess, remediate,
and coordinate disclosure before public details are shared.

## Security boundaries

Alfred coordinates local command-line tools and Git repositories. Users remain responsible for the
permissions and behavior of configured agent executables, repository remotes, tmux sessions, and
files exposed through prompts. Review `.alfred/config.toml` and generated prompt/completion content
before use in a sensitive workspace.

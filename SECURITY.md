# Security Policy

WhisperBar runs entirely on your own Mac. It records audio, transcribes it
locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and
never sends your audio or transcribed text anywhere (the only network access is
a one-time model download from Hugging Face — see the README). Because it uses
**Input Monitoring** (to detect the global hotkey) and **Accessibility** (to
paste text), the project takes security reports seriously.

## Reporting a Vulnerability

**Please do not open a public issue for a security vulnerability.**

Instead, report it privately through GitHub's built-in flow:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability** (GitHub private vulnerability reporting).
3. Describe the issue with enough detail to reproduce it.

If private reporting is unavailable to you, you may open a normal issue that
says only "requesting a private security contact" (with no details), and a
maintainer will follow up.

Helpful things to include:

- A clear description of the vulnerability and its impact.
- Steps to reproduce, or a proof of concept.
- The WhisperBar version / commit, macOS version, and how you ran it
  (`./run.sh` vs the built `.app`).
- Any relevant excerpts from `~/.whisperbar/whisperbar.log`.

## Scope

This is a small, volunteer-maintained open-source project, so responses are on
a best-effort basis. Reports that are in scope include, for example:

- Code paths that could leak recorded audio or transcribed text off the device.
- Ways a crafted `~/.whisperbar/config.json` could lead to code execution or
  loading of unintended model files.
- Command/shell injection, insecure file handling, or privilege issues in the
  app or its install scripts.

Out of scope: issues that require an attacker to already have local, same-user
code-execution access (at that point the machine is already compromised), and
vulnerabilities in third-party dependencies (please report those upstream —
see [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md)).

## Supported Versions

The latest commit on the default branch is the only supported version. Please
make sure you can reproduce an issue against it before reporting.

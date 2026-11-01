---
id: U01
title: Change Fluidra password (+ optional GitHub cache purge)
phase: 0-safety
points: 1
status: todo
depends_on: []
owner: user
---
## Why
The password has been public on GitHub; a history rewrite does not remove it from
forks (e.g. `kifeo/ha-fluidra-pool`), clones, or GitHub's cached PR refs.

## Steps for Thomas
1. Change the password in the Fluidra Pool app (Account → Change password). Enable MFA if offered.
2. Update the credentials in Home Assistant (reconfigure/reauth the integration).
3. Optional: ask GitHub Support to purge cached views/PR refs of `Roagert/ha-fluidra-pool`
   (https://support.github.com → "Remove sensitive data").

## Acceptance criteria
- [ ] Thomas confirms the old password no longer works.

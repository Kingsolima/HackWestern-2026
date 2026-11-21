# Entire CLI reference

Commands for using the Entire CLI (`entire`) in this repo. The GitHub repo is `Kingsolima/HackWestern-2026`.

Values in `<angle brackets>` only exist at run time. Get them from the output of an earlier command:

- `<id>`: a finding or checkpoint ID, from `entire trail finding` or `entire checkpoint list`
- `<branch>`: a teammate's branch name, from `git branch -a`
- `<trail-number>`: a Trail number, from `entire trail show` or entire.com
- `<commit>`: the short hash of the commit with the fix, from `git log --oneline`

## Setup (once per machine)

This is WSL with no OS keyring. `~/.config/entire/config.json` must contain `{"token_store": "file"}`, or the login won't be saved.

```bash
entire login                       # opens a browser; a human has to finish it
entire repo mirror add             # needs the Entire GitHub App on the repo
```

To clone a fresh copy:

```bash
cd ~
entire repo clone /gh/Kingsolima/HackWestern-2026 --nearest
cd HackWestern-2026
```

To enable Entire in an existing clone:

```bash
entire enable                      # choose Claude Code
entire status                      # check that sessions are being captured
```

## One Trail per feature

Use a separate branch and Trail for each feature: the swarm, the verifier, the optimizer and the frontend. This example is for the swarm:

```bash
git switch -c swap-finder-swarm
entire trail create --title "TinyFish swap-finder swarm" --type feature
entire trail watch                              # live reviews and findings
entire trail finding                            # list what review agents flagged
entire trail finding apply <id>                 # accept a suggested fix
entire trail finding resolve <id> -m "fixed in <commit>"
entire trail ready
entire trail merge
```

Add Entire's preset review agents (risk, security, drift and others). The presets run on free credit:

```bash
entire project agent add
```

## Handing work between teammates

```bash
entire session resume <branch>     # pick up a teammate's agent session with its full context
entire trail resume <trail-number> # continue a Trail with its sessions
```

## Search past work before starting over

```bash
entire search "why does the verifier reject unknown origin" --json --compact
entire checkpoint explain <id>
```

## Proof for the Devpost page (before submitting)

```bash
entire checkpoint list             # number of checkpoints
entire activity                    # activity overview and recent sessions
entire dispatch                    # written summary of recent agent work
entire trail show                  # screenshot a Trail page with its findings
```

Take screenshots of the Trail pages on entire.com too.

## Check what you're uploading

Session transcripts are pushed with the code, so a public repo makes them public.

```bash
entire checkpoint list --outgoing
```

To keep transcripts in a separate private repo (create `Kingsolima/HackWestern-2026-sessions` on GitHub as a private repo first):

```bash
entire configure --local --checkpoint-remote github:Kingsolima/HackWestern-2026-sessions
```

If judges need to see sessions, keep the repo public. Make sure no API keys or TinyFish credentials ever appear in prompts.

## Extras

```bash
entire trail comment add -m "..."          # add to a Trail's discussion
entire trail attachment add shot.png       # attach a screenshot to a Trail
entire trail rerun-review                  # run the review agents again
entire plugin search                       # find plugins
entire plugin install <name>               # install a plugin
entire doctor                              # fix stuck sessions
entire api /api/v1/me                      # call the API directly
```

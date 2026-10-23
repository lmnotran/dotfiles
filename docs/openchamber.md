# OpenChamber service

[OpenChamber](https://github.com/openchamber/openchamber), the web UI for OpenCode, runs as the systemd user service `openchamber.service` on `127.0.0.1:3000`. systemd starts it at boot and restarts it whenever it exits. `chamberctl` controls it.

## Install

```sh
./script/install-openchamber
```

It needs Linux with systemd. Re-running it is safe: each step checks first and skips what's already done.

1. Checks for `bun`, `opencode`, `chezmoi`, `python3` and `curl`, lists anything missing, and prints the install command for `bun` and `opencode`.
2. Installs OpenChamber 1.x with `bun add -g @openchamber/web@1` if it isn't installed. See [Updating OpenChamber](#updating-openchamber) for why it's 1.x.
3. Installs the unit and `chamberctl` from this repo with chezmoi, then reloads systemd.
4. Sets `"shell": "/bin/bash"` in `~/.config/opencode/opencode.json`, or in `opencode.jsonc` when that's the only config. See [Why the bash tool uses bash](#why-the-bash-tool-uses-bash).
5. Turns on lingering with `sudo loginctl enable-linger`, so the service starts at boot without a login.
6. Saves the web UI password in `~/.config/openchamber/service.env`. It copies the one `openchamber serve` uses, or asks you for one.
7. Starts the service with `chamberctl migrate`. If `openchamber serve` is running, this stops it first, which ends its agent sessions and terminals, so it asks before going ahead. `--yes` skips the question.
8. Checks that OpenChamber answers and that its OpenCode server started. OpenChamber keeps serving its page when OpenCode fails, so the page loading isn't enough.

When you run it from an OpenChamber terminal, step 7 closes that terminal. The switch still finishes, because it runs in its own systemd unit. Reload the page after about 15 seconds.

## Control it

| Command | What it does |
|---|---|
| `chamberctl status` | Shows whether it's running, its PID and recent log lines |
| `chamberctl logs -f` | Follows the logs. They go to the journal, so `openchamber logs` doesn't show them |
| `chamberctl restart` | Restarts it. Ends running agent sessions and OpenChamber terminals |
| `chamberctl stop` / `start` | Stops or starts it |
| `chamberctl enable` / `disable` | Turns starting at boot on or off |

## Files

| Path | Comes from | Holds |
|---|---|---|
| `~/.config/systemd/user/openchamber.service` | [`chezmoi/private_dot_config/systemd/user/openchamber.service`](../chezmoi/private_dot_config/systemd/user/openchamber.service) | The unit |
| `~/.local/bin/chamberctl` | [`chezmoi/dot_local/bin/executable_chamberctl`](../chezmoi/dot_local/bin/executable_chamberctl) | The control script |
| `~/.config/openchamber/service.env` | The install script. Not in git | `OPENCHAMBER_UI_PASSWORD`, mode 600 |
| `~/.config/opencode/opencode.json` | Not managed. The install script sets one key | `"shell": "/bin/bash"` |

`opencode.json` stays out of chezmoi because OpenCode plugin installers rewrite it.

## Why the bash tool uses bash

Agents write bash, but OpenCode's bash tool runs `$SHELL`, which is zsh here. On zsh, ordinary bash breaks: `git show "$SHA:path"` gets mangled by zsh's `:` modifiers, a glob that matches nothing aborts the whole command, and a loop variable named `path` overwrites `PATH`.

The `shell` key in `opencode.json` switches only the bash tool. The unit leaves `SHELL` as zsh, because OpenChamber copies your login environment by running `$SHELL -lic env`. OpenChamber's terminal tabs still default to zsh.

## Updating OpenChamber

Stay on OpenChamber 1.x for now. OpenChamber 2.x needs OpenCode 2.1 or newer, and the newest OpenCode is still 1.x, so 2.x runs without OpenCode. That rules out OpenChamber's update button, because it installs the newest version, 2.x. Update within 1.x instead:

```sh
bun add -g @openchamber/web@1 && chamberctl restart
```

That works from an OpenChamber terminal too: the restart finishes even though it closes the terminal.

Skip `openchamber update` on the command line. It stops the service's process and starts an `openchamber serve` copy on the same port, and the two fight over the port when systemd restarts the service.

Once OpenCode 2.1 is out, upgrade OpenCode first. Then the update button works: under systemd it installs the update in its own job, then restarts `openchamber.service` by that name, so keep the unit's name.

## Gotchas

- `openchamber stop` only stops it for 5 seconds before systemd starts it again. Use `chamberctl stop`. `openchamber restart` works.
- `openchamber startup enable` and `disable` write or delete this same unit file. Use `chamberctl enable` and `disable`. If one of them ran, re-run the install script.
- Agent sessions get `SSH_AUTH_SOCK` and the D-Bus session from your systemd user manager. If `git push` or `gh` fails in agent sessions after a reboot, log in to the desktop once to unlock the keyring, then run `chamberctl restart`.
- After pulling a change to the unit or `chamberctl`, re-run the install script. It tells you when the running service needs a `chamberctl restart`.

## Go back to `openchamber serve`

Run these over SSH, not in an OpenChamber terminal, since stopping the service closes those terminals:

```sh
chamberctl disable
chamberctl stop
openchamber serve --ui-password '<password>'
```

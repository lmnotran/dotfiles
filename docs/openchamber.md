# OpenChamber service

[OpenChamber](https://github.com/openchamber/openchamber) is the web UI for OpenCode.
It runs as the systemd user service `openchamber.service` on `127.0.0.1:3000`.
Systemd starts it at boot and restarts it when it exits. Control it with `chamberctl`.

## Install

```sh
./script/install-openchamber
```

It needs Linux with systemd. Re-running it is safe: each step checks first and skips what's already done.

1. Checks for `bun`, `opencode`, `chezmoi`, `python3`, and `curl`. Lists missing tools and prints install commands for `bun` and `opencode`.
2. Installs OpenChamber 1.x with `bun add -g @openchamber/web@1` if it isn't installed. See [Updating OpenChamber](#updating-openchamber) for why it's 1.x.
3. Installs the unit and `chamberctl` from this repo with chezmoi, then reloads systemd.
4. Sets `"shell": "/bin/bash"` in `~/.config/opencode/opencode.json`, or in `opencode.jsonc` when that's the only config. See [Why the bash tool uses bash](#why-the-bash-tool-uses-bash).
5. Turns on lingering with `sudo loginctl enable-linger`, so the service starts at boot without a login.
6. Saves the web UI password in `~/.config/openchamber/service.env`. It copies the one `openchamber serve` uses, or asks you for one.
7. Starts the service with `chamberctl migrate`. It asks before stopping a running `openchamber serve`, since that ends its sessions and terminals. `--yes` skips the question.
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
| `~/.config/opencode/plugins/agent-git-env.js` | [`chezmoi/private_dot_config/opencode/plugins/agent-git-env.js`](../chezmoi/private_dot_config/opencode/plugins/agent-git-env.js) | Turns off commit signing for agent commands, not terminals. Loads on `chamberctl restart` |

`opencode.json` stays out of chezmoi because OpenCode plugin installers rewrite it.

## Why the bash tool uses bash

OpenCode's bash tool runs `$SHELL`, which is zsh here. Agents often write bash
commands that behave differently in zsh:

| Bash command | What zsh does |
|--------------|---------------|
| `git show "$SHA:path"` | Treats `:` as a variable modifier. |
| A glob with no matches | Aborts the command. |
| A loop variable named `path` | Overwrites `PATH`. |

The `shell` key in `opencode.json` switches only the bash tool. The unit leaves `SHELL` as zsh, because OpenChamber copies your login environment by running `$SHELL -lic env`. OpenChamber's terminal tabs still default to zsh.

## Updating OpenChamber

The [installer](../script/install-openchamber) uses OpenChamber 1.x.
OpenChamber 2.x needs OpenCode 2.1 or newer.
Without a compatible OpenCode version, the web UI runs but OpenCode doesn't.

The update button installs the newest OpenChamber version. Update within 1.x instead:

```sh
bun add -g @openchamber/web@1 && chamberctl restart
```

That works from an OpenChamber terminal too: the restart finishes even though it closes the terminal.

Use `chamberctl` rather than `openchamber update`. The latter starts an
`openchamber serve` copy on the service's port. When systemd restarts the
service, the two processes compete for that port.

To move to OpenChamber 2.x, upgrade OpenCode to 2.1 or newer first.
Then the update button can install updates and restart the systemd service.
Keep the unit named `openchamber.service`, since the updater uses that name.

## Gotchas

- `openchamber stop` only stops it for 5 seconds before systemd starts it again. Use `chamberctl stop`. `openchamber restart` works.
- `openchamber startup enable` and `disable` write or delete this same unit file. Use `chamberctl enable` and `disable`. If one of them ran, re-run the install script.
- Agent sessions get `SSH_AUTH_SOCK` and the D-Bus session from your systemd user manager.
- If `git push` or `gh` fails after a reboot, log in to the desktop to unlock the keyring. Then run `chamberctl restart`.
- After pulling a change to the unit or `chamberctl`, re-run the install script. It tells you when the running service needs a `chamberctl restart`.

## Go back to `openchamber serve`

Run these over SSH, not in an OpenChamber terminal, since stopping the service closes those terminals:

```sh
chamberctl disable
chamberctl stop
openchamber serve --ui-password '<password>'
```

// Agents' shell commands commit without GPG signing: gpg can't ask an agent for its passphrase.
// Claude Code gets the same three variables from the env block in claude-config's settings.json.
// OpenCode 2 loads this file from ~/.config/opencode/plugins/ and reloads it when it changes.
// Its shell hook covers the commands the agent runs, not interactive terminals.

export default {
  id: "agent-git-env",
  async setup(ctx) {
    await ctx.shell.hook("create.before", (event) => {
      event.env.GIT_CONFIG_COUNT = "1"
      event.env.GIT_CONFIG_KEY_0 = "commit.gpgsign"
      event.env.GIT_CONFIG_VALUE_0 = "false"
    })
  },
}

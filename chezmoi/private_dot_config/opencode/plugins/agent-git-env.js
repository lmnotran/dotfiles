// Agent commands commit without GPG signing: the bash tool and a session's `!` commands
// get commit.gpgsign=false. OpenCode terminals pass no callID, so they keep signing.
// OpenCode loads this file at startup (`chamberctl restart`).

/** @type {import("@opencode-ai/plugin").Plugin} */
export const AgentGitEnv = async () => ({
  "shell.env": async (input, output) => {
    if (!input.callID) return
    output.env.GIT_CONFIG_COUNT = "1"
    output.env.GIT_CONFIG_KEY_0 = "commit.gpgsign"
    output.env.GIT_CONFIG_VALUE_0 = "false"
  },
})

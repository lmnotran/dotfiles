return {
  {
    "williamboman/mason.nvim",
    cmd = { "Mason" },
    keys = {
      { "<leader>om", "<Cmd>Mason<CR>", desc = "Open Mason" },
    },
    config = function() require("mason").setup() end
  },

  {
    "williamboman/mason-lspconfig.nvim",
    event = { "BufReadPre", "BufNewFile" },
    opts = {
      ensure_installed = {
        "lua_ls",
        "pyright",
        "clangd",
        "bashls",
        "jsonls",
        "yamlls",
      },
    },
  },

  {
    "neovim/nvim-lspconfig",
    opts = {
      inlay_hints = {
        enabled = true
      }
    },
    event = { "BufReadPost", "BufNewFile" },
    config = function() end
  }
}

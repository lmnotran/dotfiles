return {
  {
    "folke/tokyonight.nvim",
    lazy = false,
    priority = 1000,
    config = function()
      require("tokyonight").setup({
        style="night",
        transparent = true,
      })
      vim.o.background = 'dark'
      vim.cmd[[colorscheme tokyonight]]
    end
  },

  {
    "f-person/auto-dark-mode.nvim",
    event = "VeryLazy",
    cond = function()
      return vim.uv.os_uname().sysname == "Darwin"
    end,
    config = function()
      local auto_dark_mode = require('auto-dark-mode')
      auto_dark_mode.setup({
        set_dark_mode = function()
          vim.o.background = 'dark'
          vim.cmd[[colorscheme tokyonight]]
        end,
        set_light_mode = function()
          vim.o.background = 'light'
          vim.cmd[[colorscheme tokyonight-day]]
        end
      })
      auto_dark_mode.init()
    end,
  },
}

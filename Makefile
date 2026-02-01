# Simple Makefile to manage GNU Stow dotfiles

SHELL := /bin/zsh
STOW ?= stow
UNSTOW ?= $(STOW) -D
STOW_DIR := $(CURDIR)/stow
TARGET ?= $(HOME)
PACKAGES ?= $(notdir $(wildcard $(STOW_DIR)/*))

.PHONY: help
help:
	@echo "Targets:"
	@echo "  make stow [PACKAGES=...]   # Stow selected packages to $(TARGET)"
	@echo "  make unstow [PACKAGES=...] # Unstow selected packages from $(TARGET)"
	@echo "  make restow                # Restow selected packages"
	@echo "  make dry-run               # Show what would change"
	@echo "Variables:"
	@echo "  TARGET=$(TARGET)"
	@echo "  PACKAGES=$(PACKAGES)"

.PHONY: _check
_check:
	@command -v $(STOW) >/dev/null 2>&1 || { echo "Error: stow not found"; exit 1; }
	@test -d $(STOW_DIR) || { echo "Error: missing $(STOW_DIR)"; exit 1; }

.PHONY: stow
stow: _check
	@echo "Stowing: $(PACKAGES) -> $(TARGET)"
	@$(STOW) -v -R -t $(TARGET) -d $(STOW_DIR) $(PACKAGES)

.PHONY: unstow
unstow: _check
	@echo "Unstowing: $(PACKAGES) from $(TARGET)"
	@$(UNSTOW) -v -t $(TARGET) -d $(STOW_DIR) $(PACKAGES)

.PHONY: restow
restow: _check
	@echo "Restowing: $(PACKAGES) -> $(TARGET)"
	@$(STOW) -v -R --adopt -t $(TARGET) -d $(STOW_DIR) $(PACKAGES)

.PHONY: dry-run
dry-run: _check
	@echo "Dry-run stow (no changes): $(PACKAGES) -> $(TARGET)"
	@$(STOW) -nv -R -t $(TARGET) -d $(STOW_DIR) $(PACKAGES)

.PHONY: nvim-setup
nvim-setup:
	@echo "Checking nvim plugin dependencies..."
	@command -v rg >/dev/null 2>&1 || echo "Warning: ripgrep (rg) not found - run ./script/install-deps"
	@command -v fd >/dev/null 2>&1 || echo "Warning: fd not found - run ./script/install-deps"
	@command -v lazygit >/dev/null 2>&1 || echo "Warning: lazygit not found - run ./script/install-deps"
	@command -v gcc >/dev/null 2>&1 || command -v clang >/dev/null 2>&1 || echo "Warning: C compiler not found - needed for treesitter"
	@echo "Installing nvim plugins via lazy.nvim..."
	@nvim --headless "+Lazy! restore" +qa
	@echo "Installing treesitter parsers..."
	@nvim --headless "+TSUpdateSync" +qa
	@echo "Done! Run 'nvim' to verify setup."

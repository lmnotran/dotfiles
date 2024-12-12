SPACESHIP_PROMPT_ORDER=(
  user           # Username section
  host           # Hostname section
  dir            # Current directory section
  git            # Git section (git_branch + git_status)
  package        # Package version
  node           # Node.js section
  python         # Python section
  rust           # Rust section
  docker         # Docker section
  docker_compose # Docker section
  aws            # Amazon Web Services section
  gcloud         # Google Cloud Platform section
  venv           # virtualenv section
  kubectl        # Kubectl context section
  ansible        # Ansible section
  terraform      # Terraform workspace section
  nix_shell      # Nix shell
  gnu_screen     # GNU Screen section
  exec_time      # Execution time
  async          # Async jobs indicator
  line_sep       # Line break
  jobs           # Background jobs indicator
  exit_code      # Exit code section
  sudo           # Sudo indicator
  char           # Prompt character
)
SPACESHIP_RPROMPT_ORDER=(
  time           # Time stamps section
  battery        # Battery level and status
)

# Display time
SPACESHIP_TIME_SHOW=true

# Do not truncate path in repos
SPACESHIP_DIR_TRUNC_REPO=false

################################################################################
# Username
################################################################################
SPACESHIP_USER_PREFIX=""
SPACESHIP_USER_SUFFIX=""
SPACESHIP_USER_SHOW=always
################################################################################
# Hostname
################################################################################
SPACESHIP_HOST_PREFIX="@"
SPACESHIP_HOST_SHOW=always



################################################################################
# Programming Langs
################################################################################
# java
SPACESHIP_JAVA_SHOW=false

#python
SPACESHIP_PYTHON_SHOW=false
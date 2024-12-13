# Install zsh and setup dotfiles
#
# Usage:
#   # Run the following command in the root of the repository
#   docker build -t lmnotran/02-setup-zsh -f docker/lmnotran/02-setup-zsh.dockerfile .

ARG BASE_IMAGE=ubuntu:latest
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

# Install zsh
USER root
RUN apt-get update && apt-get install -y \
        zsh \
        git \
        curl \
        && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install fzf
ENV FZF_BASE=/opt/fzf
RUN git clone --depth 1 https://github.com/junegunn/fzf.git ${FZF_BASE} \
        && ${FZF_BASE}/install --all --no-bash --no-fish


# User who will have zsh as default shell and oh-my-zsh installed.
ARG USER_NAME=mason

USER ${USER_NAME}

# Copy the dotfiles to the container
ARG dotfiles_dir=/home/${USER_NAME}/.dotfiles
COPY --chown=${USER_NAME} . ${dotfiles_dir}

# Link the dotfiles
RUN ${dotfiles_dir}/script/bootstrap link

# Set zsh as default shell
USER root
RUN chsh --shell /usr/bin/zsh ${USER_NAME}

ENV DEBIAN_FRONTEND=dialog
USER ${USER_NAME}
ENTRYPOINT [ "zsh" ]

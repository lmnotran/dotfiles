ARG BASE_IMAGE=ubuntu:latest
FROM ${BASE_IMAGE}

ARG USER_NAME=mason

USER root
RUN chsh --shell /usr/bin/zsh ${USER_NAME}
USER ${USER_NAME}

RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

ENTRYPOINT [ "zsh" ]

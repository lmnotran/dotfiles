ARG BASE_IMAGE=ubuntu:latest
FROM ${BASE_IMAGE}

ARG USER_NAME=mason

USER ${USER_NAME}

RUN curl https://pyenv.run | bash


ENV PYENV_ROOT="${HOME}/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"
ENTRYPOINT [ "zsh" ]

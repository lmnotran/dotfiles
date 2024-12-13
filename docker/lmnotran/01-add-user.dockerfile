# Creates a non-root user with sudo permissions
#
# Usage:
#   # Run the following command in the root of the repository
#   docker build -t lmnotran/01-add-user -f docker/lmnotran/01-add-user.dockerfile .
#


ARG BASE_IMAGE=ubuntu:latest
FROM ${BASE_IMAGE}

ARG USER_NAME=mason
ARG USER_UID=1000
ARG USER_GID=1000
ARG USER_GROUP_NAME=${USER_NAME}
ARG USER_HOME=/home/${USER_NAME}

USER root

# Install sudo
RUN apt-get update && apt-get install -y sudo && apt-get clean && rm -rf /var/lib/apt/lists/*

# Setup non-root user with sudo permissions
RUN (userdel $(id -n -u ${USER_UID}) && userdel ${USER_NAME} ) || true
RUN getent group ${USER_GID} || groupadd \
        --gid ${USER_GID} \
        host_${USER_GROUP_NAME} \
    && useradd -l -m \
        --home-dir ${USER_HOME} \
        --uid ${USER_UID} \
        --gid ${USER_GID} \
        --groups sudo \
        ${USER_NAME}
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER ${USER_NAME}
RUN mkdir -p ${USER_HOME}/.ssh/ \
    && chmod 700 ${USER_HOME}/.ssh/
WORKDIR ${USER_HOME}
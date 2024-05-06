ARG BASE_IMAGE=ubuntu:latest
FROM ${BASE_IMAGE}

ARG USER_NAME=mason
ARG USER_UID=1000
ARG USER_GID=1000
ARG USER_GROUP_NAME=${USER_NAME}
ARG USER_HOME=/home/${USER_NAME}

# Setup non-root user with sudo permissions
USER root

RUN (userdel $(id -n -u ${USER_UID}) && userdel ${USER_NAME} ) || true
RUN addgroup \
        --gid ${USER_GID} \
        host_${USER_GROUP_NAME} \
    && useradd -l -m \
        --home-dir ${USER_HOME} \
        --uid ${USER_UID} \
        --gid ${USER_GID} \
        --groups sudo \
        -p ***REDACTED_MYSQL_PASSWORD*** \
        ${USER_NAME}
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER ${USER_NAME}
RUN mkdir -p ${USER_HOME}/.cache/tools/images
ENV IMAGES_DIR=${USER_HOME}/.cache/tools/images

WORKDIR ${USER_HOME}
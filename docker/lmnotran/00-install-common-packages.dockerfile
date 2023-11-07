ARG BASE_IMAGE=ubuntu:latest
FROM ${BASE_IMAGE}

USER root
RUN apt-get update \
    && apt-get install -y \
        curl \
        wget \
        zsh \
        git \
        git-lfs \
        cmake \
        ninja-build \
        htop \
        sudo \
        fzf \
        coreutils \
        openjdk-17-jre \
        python3-setuptools \
        python3-pip \
        unzip \
    && rm -rf /var/lib/apt/lists/*

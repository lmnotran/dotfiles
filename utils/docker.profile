#!/bin/bash

function docker-lmno-build()
{
    DOCKER_BUILD_ARGS=(
        --build-arg USER_NAME=$(id -u -n)
        --build-arg USER_UID=$(id -u)
        # --build-arg USER_GID=$(id -g)
        # --build-arg USER_GROUP_NAME=$(id -g -n)
        --build-arg USER_HOME=${HOME}
    )
    pushd $DOTFILES/docker/lmnotran
    BASE_IMAGE=ubuntu:latest
    i=0
    for df in `ls` ; do
        cmd="docker build -f "$df" -t lmnotran:$i --build-arg BASE_IMAGE=$BASE_IMAGE ${DOCKER_BUILD_ARGS[@]} ."
        echo $cmd
        eval $cmd || return $?
        BASE_IMAGE=lmnotran:$i
        i=$((i+1))
    done
    docker tag lmnotran:$((i-1)) lmnotran:latest
    popd
}

function docker-lmno-run()
{
    COLIMA_SSH_AUTH_SOCK=$(colima ssh env | grep SSH_AUTH_SOCK | cut -d = -f 2)
    cmd="docker run \
        --rm \
        -it \
        -v $COLIMA_SSH_AUTH_SOCK:$COLIMA_SSH_AUTH_SOCK \
        -v ${HOME}:${HOME} \
        -e SSH_AUTH_SOCK=$COLIMA_SSH_AUTH_SOCK \
        --hostname docker \
        lmnotran:latest"
    echo $cmd
    eval $cmd
}
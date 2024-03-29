#!/bin/bash

add_to_path=(
    "/home/$USER/.local/bin"
    "/home/linuxbrew/.linuxbrew/bin"
    "/home/linuxbrew/.linuxbrew/sbin"
)
for p in ${add_to_path[@]}; do
    if [ ! -d "$p" ]; then
        echo "Skipping ${p}"
        continue
    fi
    export PATH="${p}:${PATH}"
done

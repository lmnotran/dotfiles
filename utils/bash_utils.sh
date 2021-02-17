#!/bin/bash

function contains() {
    list=$1
    x=$2
    [[ $list =~ (^|[[:space:]])$x($|[[:space:]]) ]] && exit(0) || exit(1)
}

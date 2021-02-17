#!/bin/zsh

REQUIRED_COMMANDS=(
	dialog
	expect
)

for CMD in ${REQUIRED_COMMANDS[@]}; do
	if ! command -v $CMD &> /dev/null
	then
	    echo "$CMD could not be found"
	    exit
	fi
done

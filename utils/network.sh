#!/bin/bash

function isHomeNetworkOld() {
    local EXTERNAL_IP=$(/usr/bin/curl -s checkip.amazonaws.com)
    local HOME_IP=$(host home.segfault.rip | grep -oP '(\d{1,3}.+)*')
    # echo "EXTERNAL_IP = $EXTERNAL_IP"
    # echo "HOME_IP = $HOME_IP"
    if [ $EXTERNAL_IP = $HOME_IP ]; then
        # Return success
        return 0
    else
        return 1
    fi
}

function isHomeNetwork() {
    local ipv4_addresses

    ipv4_addresses=$(ifconfig | grep -E "([0-9]{1,3}\.){3}[0-9]{1,3}" | grep -v 127.0.0.1 | awk '{ print $2 }' | cut -f2 -d:)
    IFS=$'\n' read -r -d '' -A ipv4_addresses <<< $ipv4_addresses
    for (( i=0; i<${#ipv4_addresses[@]}; i++ )); do
        # echo "$i: ${ipv4_addresses[$i]}"
        if [[ "${ipv4_addresses[$i]}" =~ ^192\.168\.8\.[0-9]{1,3}$ ]]; then
            # Home
            return 0
        fi
    done

    # Not home
    return 1
}
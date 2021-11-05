#!/bin/bash

function isHomeNetwork() {
    export EXTERNAL_IP=$(/usr/bin/curl -s checkip.amazonaws.com)
    export HOME_IP=$(host home.segfault.rip | grep -oP '(\d{1,3}.+)*')
    # echo "EXTERNAL_IP = $EXTERNAL_IP"
    # echo "HOME_IP = $HOME_IP"
    if [ $EXTERNAL_IP = $HOME_IP ]; then
        # Return success
        return 0
    else
        return 1
    fi
}

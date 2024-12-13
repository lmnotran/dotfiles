#!/bin/bash

# Install Ansible
python3 -m pip install --user ansible
command -v ansible-playbook > /dev/null || echo "Ansible not found"

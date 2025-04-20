#!/bin/bash

echo >> /home/mason/.zshrc
echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> /home/mason/.zshrc
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"

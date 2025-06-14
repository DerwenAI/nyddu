#!/usr/bin/env zsh
# approximate the functionality of pre-commit hooks,
# without the attitude or lack of useful docs

# TBD:
#    "run pytest"

declare -a arr=(
    "check"
    "run mypy nyddu"
    "run pylint nyddu"
)

set -e

for i in "${arr[@]}"
do
    cmd="poetry $i"
    echo $cmd
    eval $cmd
done

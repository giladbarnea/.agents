#!/usr/bin/env bash

git config --local core.hooksPath .githooks
git -C plugins/.published-soft-skills config --local core.hooksPath "$PWD/.githooks/published"

#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=lib-unloved-preflight.sh
source "$(dirname "$0")/lib-unloved-preflight.sh"

preflight_stack

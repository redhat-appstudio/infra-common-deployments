#!/usr/bin/env bash
# Compare the kustomize build output (helm always enabled) of components/<name>/<env>
# against components/<name>-ed/<env> for every environment both provide.
#
# Usage: hack/compare-component-builds.sh <component-name>
#
# Part of the repository-structure enforcement effort: use this script to test
# that a component migration to the canonical directory layout
# (shared-resources/ + shared-resources-ref/, file naming, patches/) is
# render-neutral, i.e. the component is ready to be onboarded to Kargo without
# any change in what gets deployed.
#
# Exits non-zero if any environment renders differently (or fails to build).

set -euo pipefail

COMPONENT="${1:?Usage: $0 <component-name>}"
OLD="components/${COMPONENT}"
NEW="components/${COMPONENT}-ed"

[[ -d "${OLD}" ]] || { echo "ERROR: ${OLD} not found" >&2; exit 1; }
[[ -d "${NEW}" ]] || { echo "ERROR: ${NEW} not found" >&2; exit 1; }

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

fail=0
for old_env in "${OLD}"/*/; do
    env="$(basename "${old_env}")"
    case "${env}" in
        base|shared-resources|features|k-components|OWNERS|README.md) continue ;;
    esac
    new_env="${NEW}/${env}"
    if [[ ! -d "${new_env}" ]]; then
        echo "SKIP ${env}: no ${new_env}"
        continue
    fi
    if ! kustomize build --enable-helm "${old_env}" >"${TMPDIR}/old.yaml" 2>"${TMPDIR}/old.err"; then
        echo "FAIL ${env}: old build error:"; cat "${TMPDIR}/old.err"
        fail=1
        continue
    fi
    if ! kustomize build --enable-helm "${new_env}" >"${TMPDIR}/new.yaml" 2>"${TMPDIR}/new.err"; then
        echo "FAIL ${env}: new build error:"; cat "${TMPDIR}/new.err"
        fail=1
        continue
    fi
    if diff -u "${TMPDIR}/old.yaml" "${TMPDIR}/new.yaml" >"${TMPDIR}/diff.txt"; then
        echo "PASS ${env}: identical"
    else
        echo "FAIL ${env}: build output differs:"
        cat "${TMPDIR}/diff.txt"
        fail=1
    fi
done

exit "${fail}"

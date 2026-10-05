#!/usr/bin/env bash
set -euo pipefail

umask 077

: "${CREDENTIALS_DIR:?proxy suite credential directory is required}"
: "${TEMPLATE_FILE:?PipelineRun template is required}"

RUNNER_NAMESPACE=verification-vanguard-proxy-runner
POLL_INTERVAL=${POLL_INTERVAL:-15}
RUN_TIMEOUT_SECONDS=${RUN_TIMEOUT_SECONDS:-1800}
[[ "$POLL_INTERVAL" =~ ^[0-9]+$ ]]
[[ "$RUN_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]]

# Start with one representative staging cluster. Add one representative cluster
# from each later ring only after its cluster-side suite resources are deployed.
clusters=(stone-stg-rh01)

for cluster in "${clusters[@]}"; do
  # Validate every launcher credential before contacting a cluster. Never put the
  # token on the command line or print the generated kubeconfig.
  jq -e '.token | type == "string" and length > 0' \
    "$CREDENTIALS_DIR/vanguard-proxy-$cluster" >/dev/null
done

workdir=$(mktemp -d /tmp/proxy-regression.XXXXXXXX)
export KUBECONFIG="$workdir/kubeconfig"

kube() {
  kubectl --request-timeout=30s "$@"
}

print_run_condition() {
  jq -r '
    [.status.conditions[]? | select(.type == "Succeeded")][0]
    | "PipelineRun condition: status=\(.status // "Unknown") reason=\(.reason // "Unknown") message=\(.message // "")"
  ' <<< "$1" >&2
}

cleanup() {
  rm -rf -- "$workdir"
}

trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

for cluster in "${clusters[@]}"; do
  case "$cluster" in
    stone-stg-rh01)
      server=https://api.stone-stg-rh01.l2vh.p1.openshiftapps.com:6443
      ;;
    *)
      echo "No API endpoint configured for $cluster" >&2
      exit 1
      ;;
  esac

  # The public API certificate must chain to the launcher's system roots. Do not
  # weaken this with insecure-skip-tls-verify.
  jq --arg server "$server" --arg namespace "$RUNNER_NAMESPACE" '{
    apiVersion:"v1",kind:"Config",
    clusters:[{name:"target",cluster:{server:$server}}],
    users:[{name:"bot",user:{token:.token}}],
    contexts:[{name:"target",context:{cluster:"target",user:"bot",namespace:$namespace}}],
    "current-context":"target"
  }' "$CREDENTIALS_DIR/vanguard-proxy-$cluster" > "$KUBECONFIG"

  # Each run has isolated PipelineRun and Buildah storage. Generated names allow
  # overlapping promotions and avoid collisions with Tekton Results finalizers.
  created=$(kube create -f "$TEMPLATE_FILE" -o json)
  run_name=$(jq -er '.metadata.name' <<< "$created")
  printf 'Created cluster=%s PipelineRun=%s/%s\n' \
    "$cluster" "$RUNNER_NAMESPACE" "$run_name"

  deadline=$((SECONDS + RUN_TIMEOUT_SECONDS))
  status=Unknown
  result=''
  while (( SECONDS < deadline )); do
    result=$(kube get pipelinerun "$run_name" -n "$RUNNER_NAMESPACE" -o json)
    status=$(jq -r \
      '[.status.conditions[]? | select(.type == "Succeeded")][0].status // "Unknown"' \
      <<< "$result")
    case "$status" in
      True)
        break
        ;;
      False)
        echo "Regression failed on $cluster" >&2
        print_run_condition "$result"
        echo "PipelineRun retained for diagnostics: $RUNNER_NAMESPACE/$run_name" >&2
        exit 1
        ;;
    esac
    sleep "$POLL_INTERVAL"
  done

  [[ "$status" == True ]] || {
    echo "Regression timed out on $cluster" >&2
    [[ -z "$result" ]] || print_run_condition "$result"
    echo "PipelineRun retained for diagnostics: $RUNNER_NAMESPACE/$run_name" >&2
    exit 1
  }

  # Keep completed PipelineRuns and their Pods available for diagnostics. The
  # cluster's Tekton retention policy handles eventual cleanup.
  printf 'PipelineRun retained: %s/%s\n' "$RUNNER_NAMESPACE" "$run_name"
  printf 'PROXY_REGRESSION_PASSED cluster=%s\n' "$cluster"
done

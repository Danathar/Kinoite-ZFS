#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/compose.yml"

: "${GITHUB_REPOSITORY:=Danathar/Kinoite-ZFS}"
: "${REPO_URL:=https://github.com/${GITHUB_REPOSITORY}}"
: "${RUNNER_HOME:=${HOME}/.local/share/kinoite-zfs-runner}"
: "${RUNNER_INSTALL_DIR:=${RUNNER_HOME}/actions-runner}"
: "${RUNNER_WORKDIR:=${RUNNER_HOME}/work}"
: "${RUNNER_TOOLCACHE_DIR:=${RUNNER_HOME}/toolcache}"
: "${RUNNER_LABELS:=kinoite-zfs-builder,kinoite-zfs-trusted}"

DEFAULT_HOSTNAME="$(hostname -s 2>/dev/null || hostname)"
: "${RUNNER_NAME:=kinoite-zfs-builder-${DEFAULT_HOSTNAME}}"

usage() {
  cat <<'EOF'
Usage: ci/github-runner/manage.sh <command>

Commands:
  up          Create or update the runner container with a fresh registration token
  status      Show local container status and GitHub runner status
  logs        Follow container logs
  stop        Stop the runner container
  start       Start the existing runner container
  unregister  Remove the runner registration from GitHub
EOF
}

export_compose_env() {
  export REPO_URL
  export RUNNER_NAME
  export RUNNER_LABELS
  export RUNNER_INSTALL_DIR
  export RUNNER_WORKDIR
  export RUNNER_TOOLCACHE_DIR
  export RUNNER_TOKEN="${RUNNER_TOKEN:-unused}"
}

compose() {
  export_compose_env
  docker compose -f "${COMPOSE_FILE}" "$@"
}

ensure_dirs() {
  mkdir -p "${RUNNER_INSTALL_DIR}" "${RUNNER_WORKDIR}" "${RUNNER_TOOLCACHE_DIR}"
}

fetch_registration_token() {
  gh api -X POST "repos/${GITHUB_REPOSITORY}/actions/runners/registration-token" --jq .token
}

runner_summary() {
  gh api "repos/${GITHUB_REPOSITORY}/actions/runners" \
    --jq '.runners[] | select(.name == "'"${RUNNER_NAME}"'") | {name: .name, status: .status, busy: .busy, labels: [.labels[].name]}' \
    2>/dev/null || true
}

runner_id() {
  gh api "repos/${GITHUB_REPOSITORY}/actions/runners" \
    --jq '.runners[] | select(.name == "'"${RUNNER_NAME}"'") | .id' \
    2>/dev/null || true
}

cmd_up() {
  ensure_dirs
  export RUNNER_TOKEN
  RUNNER_TOKEN="$(fetch_registration_token)"
  compose up -d --build
  unset RUNNER_TOKEN
  compose ps
  runner_summary
}

cmd_status() {
  compose ps
  runner_summary
}

cmd_logs() {
  compose logs --tail=100 -f runner
}

cmd_stop() {
  compose stop runner
}

cmd_start() {
  compose start runner
  compose ps
  runner_summary
}

cmd_unregister() {
  local id
  id="$(runner_id)"
  if [[ -z "${id}" ]]; then
    echo "Runner ${RUNNER_NAME} is not registered in ${GITHUB_REPOSITORY}."
    return 0
  fi

  gh api -X DELETE "repos/${GITHUB_REPOSITORY}/actions/runners/${id}"
  echo "Removed runner ${RUNNER_NAME} from ${GITHUB_REPOSITORY}."
}

main() {
  local command="${1:-}"
  case "${command}" in
    up)
      cmd_up
      ;;
    status)
      cmd_status
      ;;
    logs)
      cmd_logs
      ;;
    stop)
      cmd_stop
      ;;
    start)
      cmd_start
      ;;
    unregister)
      cmd_unregister
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"

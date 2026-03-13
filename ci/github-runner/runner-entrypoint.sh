#!/usr/bin/dumb-init /bin/bash
# shellcheck shell=bash

set -euo pipefail

_ACTIONS_RUNNER_DIR=${ACTIONS_RUNNER_DIR:-/actions-runner}
_IMAGE_ACTIONS_RUNNER_DIR=${IMAGE_ACTIONS_RUNNER_DIR:-/opt/actions-runner-image}

export RUNNER_ALLOW_RUNASROOT=1
export PATH="${PATH}:${_ACTIONS_RUNNER_DIR}"

# Un-export these, so that they must be passed explicitly to the environment of
# any command that needs them. This may help prevent leaks.
export -n ACCESS_TOKEN
export -n RUNNER_TOKEN
export -n APP_ID
export -n APP_PRIVATE_KEY

trap_with_arg() {
  func="$1"
  shift
  for sig; do
    trap "$func $sig" "$sig"
  done
}

deregister_runner() {
  echo "Caught $1 - Deregistering runner"
  cd "${_ACTIONS_RUNNER_DIR}"
  if [[ -n "${ACCESS_TOKEN:-}" ]]; then
    if [[ -n "${APP_ID:-}" ]] && [[ -n "${APP_PRIVATE_KEY:-}" ]] && [[ -n "${APP_LOGIN:-}" ]]; then
      echo "Refreshing access token for deregistration"
      nl="
"
      NEW_ACCESS_TOKEN=$(APP_ID="${APP_ID}" APP_PRIVATE_KEY="${APP_PRIVATE_KEY//\\n/${nl}}" APP_LOGIN="${APP_LOGIN}" bash /app_token.sh)
      if [[ -z "${NEW_ACCESS_TOKEN}" ]] || [[ "${NEW_ACCESS_TOKEN}" == "null" ]]; then
        echo "ERROR: Failed to refresh access token for deregistration"
        exit 1
      fi
      ACCESS_TOKEN="${NEW_ACCESS_TOKEN}"
      echo "Access token refreshed successfully"
    fi
    _TOKEN=$(ACCESS_TOKEN="${ACCESS_TOKEN}" bash /token.sh)
    RUNNER_TOKEN=$(echo "${_TOKEN}" | jq -r .token)
  fi
  ./config.sh remove --token "${RUNNER_TOKEN}"
  [[ -f "${_ACTIONS_RUNNER_DIR}/.runner" ]] && rm -f "${_ACTIONS_RUNNER_DIR}/.runner"
  exit
}

_DEBUG_ONLY=${DEBUG_ONLY:-false}
_DISABLE_AUTOMATIC_DEREGISTRATION=${DISABLE_AUTOMATIC_DEREGISTRATION:-false}
_RANDOM_RUNNER_SUFFIX=${RANDOM_RUNNER_SUFFIX:=true}

_RUNNER_NAME=${RUNNER_NAME:-${RUNNER_NAME_PREFIX:-github-runner}-$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c 13; echo '')}
if [[ ${RANDOM_RUNNER_SUFFIX} != "true" ]]; then
  if [[ -f "/etc/hostname" ]] && [[ $(stat --printf="%s" /etc/hostname) -ne 0 ]]; then
    _RUNNER_NAME_PREFIX=${RUNNER_NAME_PREFIX-"github-runner"}
    _RUNNER_NAME=${RUNNER_NAME:-${_RUNNER_NAME_PREFIX:+${_RUNNER_NAME_PREFIX}-}$(cat /etc/hostname)}
    echo "RANDOM_RUNNER_SUFFIX is ${RANDOM_RUNNER_SUFFIX}. Setting runner name to ${_RUNNER_NAME}"
  fi
fi

_RUNNER_WORKDIR=${RUNNER_WORKDIR:-/_work/${_RUNNER_NAME}}
_LABELS=${RUNNER_LABELS:-${LABELS:-default}}
_RUNNER_GROUP=${RUNNER_GROUP:-Default}
_GITHUB_HOST=${GITHUB_HOST:=github.com}
_UNSET_CONFIG_VARS=${UNSET_CONFIG_VARS:=false}

if [[ -z ${RUNNER_SCOPE:-} ]]; then
  export RUNNER_SCOPE="repo"
fi

RUNNER_SCOPE="${RUNNER_SCOPE,,}"

case ${RUNNER_SCOPE} in
  org*)
    [[ -z ${ORG_NAME:-} ]] && { echo "ORG_NAME required for org runners"; exit 1; }
    _SHORT_URL="https://${_GITHUB_HOST}/${ORG_NAME}"
    RUNNER_SCOPE="org"
    if [[ -n "${APP_ID:-}" ]] && [[ -z "${APP_LOGIN:-}" ]]; then
      APP_LOGIN=${ORG_NAME}
    fi
    ;;
  ent*)
    [[ -z ${ENTERPRISE_NAME:-} ]] && { echo "ENTERPRISE_NAME required for enterprise runners"; exit 1; }
    _SHORT_URL="https://${_GITHUB_HOST}/enterprises/${ENTERPRISE_NAME}"
    RUNNER_SCOPE="enterprise"
    ;;
  *)
    [[ -z ${REPO_URL:-} ]] && { echo "REPO_URL required for repo runners"; exit 1; }
    _SHORT_URL=${REPO_URL}
    RUNNER_SCOPE="repo"
    if [[ -n "${APP_ID:-}" ]] && [[ -z "${APP_LOGIN:-}" ]]; then
      APP_LOGIN=${REPO_URL%/*}
      APP_LOGIN=${APP_LOGIN##*/}
    fi
    ;;
esac

configure_runner() {
  local args=()

  cd "${_ACTIONS_RUNNER_DIR}"

  if [[ -n "${APP_ID:-}" ]] && [[ -n "${APP_PRIVATE_KEY:-}" ]] && [[ -n "${APP_LOGIN:-}" ]]; then
    if [[ -n "${ACCESS_TOKEN:-}" ]] || [[ -n "${RUNNER_TOKEN:-}" ]]; then
      echo "ERROR: ACCESS_TOKEN or RUNNER_TOKEN provided but are mutually exclusive with APP_ID, APP_PRIVATE_KEY and APP_LOGIN." >&2
      exit 1
    fi
    echo "Obtaining access token for app_id ${APP_ID} and login ${APP_LOGIN}"
    nl="
"
    ACCESS_TOKEN=$(APP_ID="${APP_ID}" APP_PRIVATE_KEY="${APP_PRIVATE_KEY//\\n/${nl}}" APP_LOGIN="${APP_LOGIN}" bash /app_token.sh)
  elif [[ -n "${APP_ID:-}" ]] || [[ -n "${APP_PRIVATE_KEY:-}" ]] || [[ -n "${APP_LOGIN:-}" ]]; then
    echo "ERROR: All of APP_ID, APP_PRIVATE_KEY and APP_LOGIN must be specified." >&2
    exit 1
  fi

  if [[ -n "${ACCESS_TOKEN:-}" ]]; then
    echo "Obtaining the token of the runner"
    _TOKEN=$(ACCESS_TOKEN="${ACCESS_TOKEN}" bash /token.sh)
    RUNNER_TOKEN=$(echo "${_TOKEN}" | jq -r .token)
  fi

  if [[ -n "${EPHEMERAL:-}" ]]; then
    args+=("--ephemeral")
  fi
  if [[ -n "${DISABLE_AUTO_UPDATE:-}" ]]; then
    args+=("--disableupdate")
  fi
  if [[ -n "${NO_DEFAULT_LABELS:-}" ]]; then
    args+=("--no-default-labels")
  fi

  echo "Configuring"
  ./config.sh \
    --url "${_SHORT_URL}" \
    --token "${RUNNER_TOKEN}" \
    --name "${_RUNNER_NAME}" \
    --work "${_RUNNER_WORKDIR}" \
    --labels "${_LABELS}" \
    --runnergroup "${_RUNNER_GROUP}" \
    --unattended \
    --replace \
    "${args[@]}"

  [[ ! -d "${_RUNNER_WORKDIR}" ]] && mkdir -p "${_RUNNER_WORKDIR}"
}

seed_runner_files() {
  mkdir -p "${_ACTIONS_RUNNER_DIR}"
  if [[ ! -x "${_ACTIONS_RUNNER_DIR}/bin/Runner.Listener" ]]; then
    echo "Seeding runner files into ${_ACTIONS_RUNNER_DIR}"
    cp -a "${_IMAGE_ACTIONS_RUNNER_DIR}/." "${_ACTIONS_RUNNER_DIR}"
  fi
}

unset_config_vars() {
  unset RUNNER_NAME RUNNER_NAME_PREFIX RANDOM_RUNNER_SUFFIX ACCESS_TOKEN APP_ID APP_PRIVATE_KEY
  unset APP_LOGIN RUNNER_SCOPE ORG_NAME ENTERPRISE_NAME LABELS REPO_URL RUNNER_TOKEN RUNNER_WORKDIR
  unset RUNNER_GROUP GITHUB_HOST DISABLE_AUTOMATIC_DEREGISTRATION
  unset EPHEMERAL DISABLE_AUTO_UPDATE NO_DEFAULT_LABELS UNSET_CONFIG_VARS ACTIONS_RUNNER_DIR
}

echo "Runner reusage is enabled"
seed_runner_files
if [[ ! -f "${_ACTIONS_RUNNER_DIR}/.runner" ]] && [[ ${_DEBUG_ONLY} == "false" ]]; then
  configure_runner
fi

if [[ ${_DISABLE_AUTOMATIC_DEREGISTRATION} == "false" ]] && [[ ${_DEBUG_ONLY} == "false" ]]; then
  trap_with_arg deregister_runner SIGINT SIGQUIT SIGTERM INT TERM QUIT
fi

if [[ ${_UNSET_CONFIG_VARS} == "true" ]]; then
  unset_config_vars
fi

cd "${_ACTIONS_RUNNER_DIR}"
exec "$@"

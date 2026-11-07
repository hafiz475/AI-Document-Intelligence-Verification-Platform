#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

readonly deploy_root="/opt/assureai"
readonly incoming_root="${deploy_root}/incoming"
readonly releases_root="${deploy_root}/releases"
readonly environment_file="${deploy_root}/.env.production"
readonly lock_file="${deploy_root}/deploy.lock"

mkdir -p "${incoming_root}" "${releases_root}"

exec 9>"${lock_file}"
if ! flock -n 9; then
  echo "Another AssureAI deployment is already running." >&2
  exit 1
fi

if [[ ! -f "${environment_file}" ]]; then
  echo "Missing ${environment_file}; refusing to deploy." >&2
  exit 1
fi

archive_path=$(mktemp "${incoming_root}/release.XXXXXX.tar.gz")

cleanup_archive() {
  case "${archive_path}" in
    "${incoming_root}"/release.*.tar.gz)
      rm -f -- "${archive_path}"
      ;;
    *)
      echo "Refusing to remove unexpected archive path." >&2
      ;;
  esac
}
trap cleanup_archive EXIT

cat > "${archive_path}"

if tar -tzf "${archive_path}" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
  echo "Release archive contains an unsafe path." >&2
  exit 1
fi

release_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
release_dir="${releases_root}/${release_id}"
mkdir "${release_dir}"
tar --extract --gzip --file "${archive_path}" --directory "${release_dir}" --no-same-owner --no-same-permissions

for required_file in docker-compose.prod.yml .deploy-revision; do
  if [[ ! -f "${release_dir}/${required_file}" ]]; then
    echo "Release is missing ${required_file}." >&2
    exit 1
  fi
done

revision=$(tr -d '\r\n' < "${release_dir}/.deploy-revision")
if [[ ! "${revision}" =~ ^[0-9a-f]{40,64}$ ]]; then
  echo "Release revision is invalid." >&2
  exit 1
fi

cd "${release_dir}"
export COMPOSE_PARALLEL_LIMIT=1

compose=(
  docker compose
  --env-file "${environment_file}"
  -f docker-compose.prod.yml
)

"${compose[@]}" config --quiet
"${compose[@]}" --progress plain build api
"${compose[@]}" --progress plain build worker
"${compose[@]}" --progress plain build web
"${compose[@]}" up -d

ready=false
for attempt in $(seq 1 24); do
  if curl --fail --silent --show-error --max-time 5 http://127.0.0.1/ready >/dev/null; then
    ready=true
    break
  fi
  sleep 5
done

if [[ "${ready}" != true ]]; then
  "${compose[@]}" ps >&2
  "${compose[@]}" logs --tail 200 >&2
  echo "AssureAI did not become ready after deployment." >&2
  exit 1
fi

temporary_link="${deploy_root}/.current-${release_id}"
ln -s "${release_dir}" "${temporary_link}"
mv -Tf "${temporary_link}" "${deploy_root}/current"
printf '%s\n' "${revision}" > "${deploy_root}/last-deployed-revision"

"${compose[@]}" ps
echo "AssureAI deployment ${revision} is ready."

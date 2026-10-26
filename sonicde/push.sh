#!/bin/bash
#
# Push SonicDE's .debs (package-sonicde.py) to ghcr.io/rations/pivuan-sonicde/debs:<version>. The
# "Publish SonicDE" workflow of rations/pivuan-sonicde takes them from there into its apt
# repository (https://rations.github.io/pivuan-sonicde): nothing is compiled on GitHub.
#
# Usage (on the PC as yourself): sonicde/push.sh [<work-dir>] [<version>]
#   work-dir  the build root's directory (default: ~/sonicde-build); the .debs are in
#             <work-dir>/work/debs/<version>
#   version   default: the newest there
# Then run the workflow with that version (Actions > Publish SonicDE > Run workflow).
#
# Needs oras (sudo apt install oras) and the ghcr.io login the kernel uses
# (../build/.github/pivuan/kernel-build.sh --login: a classic token with write:packages), kept in
# ~/.config/pivuan/ghcr-login.json. After the first push, make the package public once (on
# github.com: rations > Packages > pivuan-sonicde/debs > Package settings > Change visibility),
# so the workflow can pull it.
#
# A version is pushed once: a published version is never reused, so a rebuild needs a new revision
# in sonicde.conf.
#
set -euo pipefail

work="$(realpath -m "${1:-${HOME}/sonicde-build}")"
debs_root="${work}/work/debs"
repo=ghcr.io/rations/pivuan-sonicde/debs
packages=(sonicde sonicde-qt sonicde-frameworks sonicde-workspace sonicde-apps sonicde-icons
	sonicde-l10n sonicde-wallpapers)

command -v oras > /dev/null || { echo "oras is missing: sudo apt install oras" >&2; exit 1; }
auth="${XDG_CONFIG_HOME:-${HOME}/.config}/pivuan/ghcr-login.json"
[[ -e "${auth}" ]] || {
	echo "no ghcr.io login: ../build/.github/pivuan/kernel-build.sh --login" >&2
	exit 1
}

if [[ -n "${2:-}" ]]; then
	version="$2"
else
	version="$(find "${debs_root}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2> /dev/null \
		| sort -V | tail -1)"
	[[ -n "${version}" ]] || { echo "no packages in ${debs_root}: run package-sonicde.py" >&2; exit 1; }
fi
dir="${debs_root}/${version}"

# All of them, at that version, and nothing else
files=()
for pkg in "${packages[@]}"; do
	match=("${dir}/${pkg}_${version}_"*.deb)
	[[ -e "${match[0]}" ]] || { echo "${pkg} ${version} is missing in ${dir}" >&2; exit 1; }
	[[ "$(dpkg-deb -f "${match[0]}" Version)" == "${version}" ]] \
		|| { echo "${match[0]##*/} is not version ${version}" >&2; exit 1; }
	files+=("${match[0]##*/}")
done
extra="$(find "${dir}" -maxdepth 1 -name '*.deb' | wc -l)"
(( extra == ${#packages[@]} )) || { echo "${dir} has other .deb files too" >&2; exit 1; }

if oras manifest fetch --registry-config "${auth}" "${repo}:${version}" > /dev/null 2>&1; then
	echo "${repo}:${version} is there already: a version is pushed once (new revision in sonicde.conf)" >&2
	exit 1
fi

echo "Pushing SonicDE ${version} ($(du -ch "${files[@]/#/${dir}/}" | tail -1 | cut -f1)) to ${repo}"
(
	cd "${dir}"
	oras push --registry-config "${auth}" \
		--annotation "org.opencontainers.image.description=Pivuan SonicDE ${version} (.debs)" \
		--annotation "org.opencontainers.image.source=https://github.com/rations/pivuan-sonicde" \
		"${repo}:${version}" "${files[@]/%/:application/vnd.debian.binary-package}"
)
oras manifest fetch --registry-config "${auth}" "${repo}:${version}" > /dev/null
echo "Pushed: ${repo}:${version}"
echo "Next: rations/pivuan-sonicde > Actions > Publish SonicDE > Run workflow, version ${version}"

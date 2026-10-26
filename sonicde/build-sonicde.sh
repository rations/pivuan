#!/bin/bash
#
# Build SonicDE into /opt/sonicde, one repo at a time, from sonicde.lock (plan-sonicde.py).
#
# Usage (inside the build root: enter-root.sh <work-dir> /src/sonicde/build-sonicde.sh ...):
#   deps                      install the Devuan packages the lock lists (once, and after a new lock)
#   status                    how many repos are done, and what is next
#   [--minutes N] [what...]   build; what = frameworks, workspace, apps or repo names (default:
#                             all), with whatever they need that is not built yet
#
# It can stop at any time and carry on later:
#   - each repo is installed into /opt/sonicde as soon as it is built, and never built again
#     (delete /work/sonic-build/<repo> to build it again);
#   - a repo that stopped part way carries on in its build tree;
#   - --minutes N starts no new repo after N minutes, and `touch <work-dir>/work/stop` (outside
#     the root) stops after the repo being built.
# Ctrl+C and a normal shutdown are safe; cutting the power during a compile can leave a broken
# object file: delete that repo's build tree.
#
# Qt comes from build-qt.sh, in the same prefix: ECM puts plugins and QML where Qt has them, and
# every binary gets /opt/sonicde/lib as its RPATH. No Python bindings, Qt 5, tests or docs.
#
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lock="${here}/sonicde.lock"
prefix=/opt/sonicde
build_root=/work/sonic-build
logs=/work/logs
jobs="${JOBS:-$(( $(awk '/MemTotal/ { print int($2 / 1048576) }' /proc/meminfo) - 2 ))}"
(( jobs > $(nproc) )) && jobs="$(nproc)"
(( jobs < 1 )) && jobs=1

[[ -e "${lock}" ]] || { echo "no ${lock}: run plan-sonicde.py on the PC" >&2; exit 1; }
mkdir -p "${build_root}" "${logs}"

# The lock's repos, in build order: group name dir commit ref [options...]
mapfile -t repos < <(awk '$1 == "repo" { $1 = ""; sub(/^ +/, ""); print }' "${lock}")

done_count() {
	local line n=0
	for line in "${repos[@]}"; do
		set -- ${line}
		[[ -e "${build_root}/$2/.installed" ]] && n=$(( n + 1 ))
	done
	echo "${n}"
}

next_repo() {
	local line
	for line in "${repos[@]}"; do
		set -- ${line}
		[[ -e "${build_root}/$2/.installed" ]] || { echo "$2"; return; }
	done
	echo "(none)"
}

case "${1:-}" in
deps)
	mapfile -t os < <(awk '$1 == "os" { for (i = 2; i <= NF; i++) print $i }' "${lock}")
	apt-get update
	apt-get install -y --no-install-recommends "${os[@]}"
	# Nothing Qt or KDE from Devuan and no libsystemd-dev
	leaks="$(dpkg-query -W -f '${Package}\n' 'libqt6*' 'qt6-*' 'libkf6*' libsystemd-dev \
		2>/dev/null || true)"
	if [[ -n "${leaks}" ]]; then
		echo "The root has packages it must not have:" >&2
		echo "${leaks}" >&2
		exit 1
	fi
	exit 0
	;;
status)
	echo "$(done_count)/${#repos[@]} repos built, next: $(next_repo)"
	for group in frameworks workspace apps; do
		n=0 total=0
		for line in "${repos[@]}"; do
			set -- ${line}
			[[ "$1" == "${group}" ]] || continue
			total=$(( total + 1 ))
			[[ -e "${build_root}/$2/.installed" ]] && n=$(( n + 1 ))
		done
		echo "  ${group}: ${n}/${total}"
	done
	[[ -e "${logs}/sonic-times.txt" ]] && awk '{ m += $3 } END { print "  " m " min so far" }' \
		"${logs}/sonic-times.txt"
	exit 0
	;;
esac

minutes=0
if [[ "${1:-}" == --minutes ]]; then
	minutes="${2:?--minutes needs a number}"
	shift 2
fi
wanted=("$@")

# What to build: the wanted repos (or groups) and every repo before them in the lock that they
# need. The lock is in dependency order, so "before" is close enough: building a few repos
# early does no harm.
last=$(( ${#repos[@]} - 1 ))
if (( ${#wanted[@]} )); then
	last=-1
	for i in "${!repos[@]}"; do
		set -- ${repos[i]}
		for w in "${wanted[@]}"; do
			[[ "$1" == "${w}" || "$2" == "${w}" ]] && last=${i}
		done
	done
	(( last >= 0 )) || { echo "nothing in the lock matches: ${wanted[*]}" >&2; exit 1; }
fi

export PATH="${prefix}/bin:${PATH}"
export PKG_CONFIG_PATH="${prefix}/lib/aarch64-linux-gnu/pkgconfig:${prefix}/lib/pkgconfig:${prefix}/share/pkgconfig"
export XDG_DATA_DIRS="${prefix}/share:/usr/share"

common=(
	-G Ninja -DCMAKE_BUILD_TYPE=Release
	-DCMAKE_INSTALL_PREFIX="${prefix}" -DCMAKE_PREFIX_PATH="${prefix}"
	-DCMAKE_INSTALL_RPATH="${prefix}/lib" -DKDE_INSTALL_USE_QT_SYS_PATHS=ON
	-DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
	-DBUILD_TESTING=OFF -DBUILD_PYTHON_BINDINGS=OFF -DBUILD_QT5=OFF -DBUILD_WITH_QT6=ON
	-DBUILD_QCH=OFF -DBUILD_DOC=OFF
)

start_all="$(date +%s)"
rm -f /work/stop
echo "== $(done_count)/${#repos[@]} repos built, ${jobs} jobs"
for i in $(seq 0 "${last}"); do
	set -- ${repos[i]}
	group="$1" name="$2" dir="/third_party/$3" commit="$4" ref="$5"
	shift 5
	build="${build_root}/${name}"
	[[ -e "${build}/.installed" ]] && continue

	if [[ -e /work/stop ]]; then
		rm -f /work/stop
		echo "== stopped as asked; next: ${name}"
		exit 0
	fi
	if (( minutes > 0 && $(date +%s) - start_all >= minutes * 60 )); then
		echo "== ${minutes} minutes are up; next: ${name}"
		exit 0
	fi

	if [[ -e "${build}/build/build.ninja" ]]; then
		echo "== ${name}: carrying on with the build in ${build}"
	else
		rm -rf "${build}"
		mkdir -p "${build}/src"
		git -c safe.directory='*' -C "${dir}" archive --format=tar "${commit}" \
			| tar -x -C "${build}/src"
		# Submodules, at the commits the repo records (plan-sonicde.py checked them out)
		git -c safe.directory='*' -C "${dir}" ls-tree -r "${commit}" \
			| awk '$2 == "commit" { print $3, $4 }' \
			| while read -r sub path; do
				git -c safe.directory='*' -C "${dir}/${path}" archive --format=tar "${sub}" \
					| tar -x -C "${build}/src/${path}"
			done
		echo "${commit} ${ref}" > "${build}/commit"
	fi
	echo "== ${name} (${group}, ${ref#origin/}): configure"
	start="$(date +%s)"
	# CMake, or Meson for a repo without CMakeLists.txt (libei); the options are its own
	if [[ -e "${build}/src/CMakeLists.txt" ]]; then
		configure=(cmake -S "${build}/src" -B "${build}/build" "${common[@]}" "$@")
	else
		configure=(meson setup --prefix="${prefix}" --buildtype=release "$@")
		[[ -e "${build}/build/build.ninja" ]] && configure+=(--reconfigure)
		configure+=("${build}/build" "${build}/src")
	fi
	# Under qemu, cmake now and then misses an installed package (Qt6Qml, Qt6Gui) and finds it
	# the next time: try once more before giving up
	if ! "${configure[@]}" > "${logs}/sonic-${name}-configure.log" 2>&1; then
		mv "${logs}/sonic-${name}-configure.log" "${logs}/sonic-${name}-configure-failed.log"
		echo "== ${name}: configure failed (${logs}/sonic-${name}-configure-failed.log), once more"
		"${configure[@]}" > "${logs}/sonic-${name}-configure.log" 2>&1 \
			|| { tail -40 "${logs}/sonic-${name}-configure.log"; exit 1; }
	fi
	echo "== ${name}: build"
	ninja -C "${build}/build" -j "${jobs}" > "${logs}/sonic-${name}-build.log" 2>&1 \
		|| { grep -A12 -m3 '^FAILED' "${logs}/sonic-${name}-build.log" \
			|| tail -40 "${logs}/sonic-${name}-build.log"; exit 1; }
	ninja -C "${build}/build" install > "${logs}/sonic-${name}-install.log" 2>&1 \
		|| { tail -40 "${logs}/sonic-${name}-install.log"; exit 1; }
	end="$(date +%s)"
	# Keep only what packaging needs: which files are this repo's (Meson lists them in its
	# install log, after comment lines)
	if [[ -e "${build}/build/install_manifest.txt" ]]; then
		cp "${build}/build/install_manifest.txt" "${build}/install_manifest.txt"
	else
		grep -v '^#' "${build}/build/meson-logs/install-log.txt" > "${build}/install_manifest.txt"
	fi
	rm -rf "${build}/build" "${build}/src"
	touch "${build}/.installed"
	printf '%s %s %d min\n' "$(date -I)" "${name}" "$(( (end - start) / 60 ))" \
		>> "${logs}/sonic-times.txt"
	echo "== ${name}: done in $(( (end - start) / 60 )) min ($(done_count)/${#repos[@]})"
done
echo "== $(done_count)/${#repos[@]} repos built; next: $(next_repo)"

#!/bin/bash
#
# Build Qt (the version in sonicde.conf) into /opt/sonicde, for SonicDE.
#
# Usage (inside the build root: enter-root.sh <work-dir> /src/sonicde/build-qt.sh [module...]):
#   no modules: all of them, in order; modules already installed are skipped
#   (delete /work/qt-build/<module> to build one again). A module that stopped part way is
#   configured again in its build tree and carries on from there.
#
# X11 only (no Wayland, EGLFS, LinuxFB or VNC), no journald, no QtWebEngine; release build with
# Qt's default RPATH, so programs in /opt/sonicde find Qt without LD_LIBRARY_PATH. The time each
# module took is added to /work/logs/qt-times.txt.
#
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
prefix=/opt/sonicde
version="$(awk '!/^#/ && $1 == "qt" { print $2 }' "${here}/sonicde.conf")"
src_dir="/qt-src/${version}"
build_root=/work/qt-build
# Each compile under qemu needs about 1 GB; leave some memory for the linker.
jobs="${JOBS:-$(( $(awk '/MemTotal/ { print int($2 / 1048576) }' /proc/meminfo) - 2 ))}"
(( jobs > $(nproc) )) && jobs="$(nproc)"
(( jobs < 1 )) && jobs=1

all=(qtbase qtshadertools qtsvg qtimageformats qtdeclarative qt5compat qttools qtwebsockets
	qtpositioning qtsensors qtmultimedia qtspeech)
modules=("${@:-${all[@]}}")

# Options per module, on top of the common ones
declare -A options=(
	[qtbase]="-DFEATURE_xcb=ON -DFEATURE_xcb_sm=ON -DFEATURE_xkbcommon_x11=ON -DFEATURE_openssl_linked=ON
		-DFEATURE_journald=OFF -DFEATURE_gtk3=OFF -DFEATURE_eglfs=OFF -DFEATURE_linuxfb=OFF
		-DFEATURE_vnc=OFF -DFEATURE_wayland=OFF -DFEATURE_sql_mysql=OFF -DFEATURE_sql_psql=OFF
		-DFEATURE_sql_odbc=OFF -DFEATURE_sql_ibase=OFF"
	[qttools]="-DFEATURE_clang=OFF -DFEATURE_qdoc=OFF"
	[qtmultimedia]="-DFEATURE_gstreamer=OFF -DFEATURE_ffmpeg=ON"
)

mkdir -p "${build_root}" /work/logs
for module in "${modules[@]}"; do
	build="${build_root}/${module}"
	if [[ -e "${build}/.installed" ]]; then
		echo "== ${module}: installed already"
		continue
	fi
	if [[ -e "${build}/build/build.ninja" ]]; then
		echo "== ${module}: carrying on with the build in ${build}"
	else
		tarball="${module}-everywhere-src-${version}.tar.xz"
		(cd "${src_dir}" && grep " ${tarball}\$" "${here}/qt.sha256" | sha256sum -c --quiet -) \
			|| { echo "${tarball}: missing or checksum mismatch" >&2; exit 1; }
		rm -rf "${build}"
		mkdir -p "${build}"
		tar -xf "${src_dir}/${tarball}" -C "${build}"
	fi
	echo "== ${module}: configure"
	start="$(date +%s)"
	# shellcheck disable=SC2086  # options holds several words
	cmake -S "${build}/${module}-everywhere-src-${version}" -B "${build}/build" -G Ninja \
		-DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="${prefix}" \
		-DCMAKE_PREFIX_PATH="${prefix}" \
		-DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
		-DQT_BUILD_TESTS=OFF -DQT_BUILD_EXAMPLES=OFF ${options[${module}]:-} \
		> "/work/logs/qt-${module}-configure.log" 2>&1 \
		|| { tail -40 "/work/logs/qt-${module}-configure.log"; exit 1; }
	echo "== ${module}: build (${jobs} jobs)"
	ninja -C "${build}/build" -j "${jobs}" > "/work/logs/qt-${module}-build.log" 2>&1 \
		|| { tail -40 "/work/logs/qt-${module}-build.log"; exit 1; }
	ninja -C "${build}/build" install > "/work/logs/qt-${module}-install.log" 2>&1 \
		|| { tail -40 "/work/logs/qt-${module}-install.log"; exit 1; }
	end="$(date +%s)"
	# Keep only what packaging needs: the install manifest says which files are this module's.
	cp "${build}/build/install_manifest.txt" "${build}/install_manifest.txt"
	rm -rf "${build}/build" "${build}/${module}-everywhere-src-${version}"
	touch "${build}/.installed"
	printf '%s %s %d min\n' "$(date -I)" "${module}" "$(( (end - start) / 60 ))" \
		| tee -a /work/logs/qt-times.txt
done

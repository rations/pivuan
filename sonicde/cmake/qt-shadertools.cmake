# sonic-workspace-addons' Picture of the Day wallpaper calls qt_add_shaders without looking for Qt
# ShaderTools: upstream gets it through Qt Quick 3D (optional), which Pivuan does not build.
# Loaded through CMAKE_PROJECT_INCLUDE (sonicde.conf).
find_package(Qt6 CONFIG REQUIRED COMPONENTS ShaderTools)

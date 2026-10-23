// 3D check of the pedalboard: the board as KiCad exports it, the Pi 5 under it on its
// header, the rear-panel test piece, and models of the parts KiCad has none for.
// Written by pcb/gen/panel.py; don't edit by hand. Same frame as rear-panel-test.scad.
// Needs ../kicad/out/3d/board.stl (panel.py exports it).
include <rear-panel-test.scad>
use <parts.scad>

show_cooler = true;
color("green") translate([0, 0, -1.6]) import("../kicad/out/3d/board.stl");
// The Pi: its x runs from the rear (SD) edge toward the front, its y across from the
// port edge; its header pin 1 under the board's (board.py: x = -49.0 + Pi y).
multmatrix([[0, 1, 0, -49.0], [-1, 0, 0, 0], [0, 0, 1, -12.6], [0, 0, 0, 1]])
    pi5(show_cooler);
color("silver") translate([25, 0, 0]) sj1_3543();  // J18
color("silver") translate([44, 0, 0]) nmj6hcd2();  // J17
color("silver") translate([66, 0, 0]) nmj6hcd2();  // J8
color("silver") translate([86, 0, 0]) rk09l_dual();  // RV3
color("silver") translate([106, 0, 0]) nmj6hcd2();  // J7
color("silver") translate([128, 0, 0]) nmj6hcd2();  // J6
color("silver") translate([148, 0, 0]) rk09l_dual();  // RV2
color("silver") translate([173, 0, 0]) rk09l_dual();  // RV1
color("silver") translate([194, 0, 0]) nmj6hcd2();  // J5

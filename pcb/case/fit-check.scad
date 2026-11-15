// 3D check of the Pivuan audio box: the board as KiCad exports it, the Pi 5 under its
// header strip, the screen, the case, and models of the parts KiCad has none for.
// Written by pcb/gen/panel.py; don't edit by hand. Frame as in dims.scad.
// Needs ../kicad/out/3d/board.stl (panel.py exports it).
include <dims.scad>
use <parts.scad>
use <case.scad>

show_cooler = true;
show_case = true;
show_top = true;

color("green") translate([0, 0, -pcb]) import("../kicad/out/3d/board.stl");
pi_place() pi5(show_cooler);
color("silver") translate([14, 0, 0]) nmj6hcd2();  // J5
color("silver") translate([35, 0, 0]) rk09l_dual();  // RV1
color("silver") translate([60, 0, 0]) rk09l_dual();  // RV2
color("silver") translate([80, 0, 0]) nmj6hcd2();  // J6
color("silver") translate([102, 0, 0]) nmj6hcd2();  // J7
color("silver") translate([122, 0, 0]) rk09l_dual();  // RV3
color("silver") translate([142, 0, 0]) nmj6hcd2();  // J8
if (show_case) {
    color("tan", 0.5) { base(); rear_panel(); }
    if (show_top) { color("tan", 0.5) top(); screen_place() screen(); tabs(); }
}

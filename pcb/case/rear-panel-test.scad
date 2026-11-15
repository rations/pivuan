// Rear panel test print for the Pivuan audio box: the board's jack, pot, LED and button
// holes. Written by pcb/gen/panel.py from the board layout; don't edit by hand.
// Print it face down. Try it on the parts, and on board-1to1.pdf printed at 100 %.
include <dims.scad>

module rear_panel_test() {
    difference() {
        union() {
            translate([-2, 0, -4.6]) cube([169.0, wall, 21.6]);
            // the ledge the board's edge rests on
            difference() {
                translate([0, -1.5, -3.6]) cube([165.0, 1.5, 2.0]);
                translate([157.38, -2.50, -4.60]) cube([2.75, 3.50, 4.00]);
                translate([161.88, -2.50, -4.60]) cube([2.75, 3.50, 4.00]);
            }
        }
        rear_cuts();
    }
}

rear_panel_test();

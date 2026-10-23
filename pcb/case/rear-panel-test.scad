// Rear panel test print for the Pivuan pedalboard: the board's jack, pot, LED and button
// holes. Written by pcb/gen/panel.py from the board layout; don't edit by hand.
// Print it face down. Try it on the parts, and on board-1to1.pdf printed at 100 %.
// x along the panel as on the board, y = 0 the inner face (outside toward +y, the board
// toward -y, as in KiCad's 3D export), z = 0 the board's top.
$fn = 64;

difference() {
    union() {
        translate([-2, 0, -4.6]) cube([212.0, 3.0, 21.6]);
        // the ledge the board's edge rests on
        difference() {
            translate([0, -1.5, -3.6]) cube([208.0, 1.5, 2.0]);
            translate([-0.00, -2.5, -4.6]) cube([7.00, 3.5, 4.0]);
            translate([8.38, -2.5, -4.6]) cube([2.75, 3.5, 4.0]);
            translate([12.88, -2.5, -4.6]) cube([2.75, 3.5, 4.0]);
            translate([28.35, -2.5, -4.6]) cube([3.30, 3.5, 4.0]);
            translate([18.35, -2.5, -4.6]) cube([3.30, 3.5, 4.0]);
            translate([23.35, -2.5, -4.6]) cube([3.30, 3.5, 4.0]);
        }
    }
    // SW1: PTS645
    translate([12, -1, 3.5]) rotate([-90, 0, 0]) cylinder(d = 4.0, h = 5.0);
    // J18: SJ1-3543
    translate([25, -1, 5.2]) rotate([-90, 0, 0]) cylinder(d = 6.4, h = 5.0);
    translate([25, 4.0, 5.2]) rotate([90, 0, 0]) cylinder(d = 10.0, h = 2.5);
    // J17: NMJ6HCD2
    translate([44, -1, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11.4, h = 5.0);
    // J8: NMJ6HCD2
    translate([66, -1, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11.4, h = 5.0);
    // RV3: RK09L
    translate([86, -1, 6.5]) rotate([-90, 0, 0]) cylinder(d = 9.5, h = 5.0);
    translate([84.8, -1, -0.3]) cube([2.4, 2.2, 1.6]);
    // J7: NMJ6HCD2
    translate([106, -1, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11.4, h = 5.0);
    // J6: NMJ6HCD2
    translate([128, -1, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11.4, h = 5.0);
    // RV2: RK09L
    translate([148, -1, 6.5]) rotate([-90, 0, 0]) cylinder(d = 9.5, h = 5.0);
    translate([146.8, -1, -0.3]) cube([2.4, 2.2, 1.6]);
    // D5: LED3
    translate([161, -1, 6.0]) rotate([-90, 0, 0]) cylinder(d = 3.2, h = 5.0);
    // RV1: RK09L
    translate([173, -1, 6.5]) rotate([-90, 0, 0]) cylinder(d = 9.5, h = 5.0);
    translate([171.8, -1, -0.3]) cube([2.4, 2.2, 1.6]);
    // J5: NMJ6HCD2
    translate([194, -1, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11.4, h = 5.0);
}

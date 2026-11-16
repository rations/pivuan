// Sizes of the Pivuan audio box, and the cut-outs and bosses its case parts share.
// Written by pcb/gen/panel.py from the board layout and the Pi 5's measured model; don't
// edit by hand. Frame: x along the rear panel as on the board, y = 0 the rear panel's inner
// face (outside toward +y), z = 0 the board's top surface.
wall = 3.0;  // rear panel and walls
floor_t = 3.0;
pcb = 1.6;
board_w = 176.0;  board_d = 86.0;
notch_x = 168.0;  notch_y = 21.0;  // the board's cut-out over the Pi's USB sockets
z_pi = -12.6;  // the Pi board's top: 11.0 mm under our board
pi_pcb = 1.3;
z_floor = -17.9;  // the floor's inner surface: the Pi stands 4.0 mm over it
pi_x0 = 225.0;  // x of the Pi's edge with the USB-C and HDMI sockets
pi_y0 = -85.5;  // y of the Pi's SD-card edge
x_right = 227.0;  // the inner face of the side wall beside the Pi
board_holes = [[3.5, -82.5], [3.5, -46.0], [88, -69], [128, -82.5]];  // M3, to case bosses
pi_holes = [[221.50, -82.00], [221.50, -24.00], [172.50, -82.00], [172.50, -24.00]];  // M2.5

// Puts a model drawn in the Pi's own frame (parts.scad) where the Pi sits.
module pi_place() {
    multmatrix([[0, -1, 0, 225.0], [1, 0, 0, -85.5], [0, 0, 1, -12.6], [0, 0, 0, 1]]) children();
}

// Everything cut out of the rear panel (which fills 0 < y < wall).
module rear_cuts() {
    // J5: NMJ6HCD2
    translate([14, -1, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11.4, h = wall + 2, $fn = 64);
    // RV1: RK09L
    translate([35, -1, 6.5]) rotate([-90, 0, 0]) cylinder(d = 9.5, h = wall + 2, $fn = 64);
    translate([33.8, -1, -0.3]) cube([2.4, 2.2, 1.6]);
    // D5: LED3
    translate([47, -1, 6.0]) rotate([-90, 0, 0]) cylinder(d = 3.2, h = wall + 2, $fn = 64);
    // RV2: RK09L
    translate([60, -1, 6.5]) rotate([-90, 0, 0]) cylinder(d = 9.5, h = wall + 2, $fn = 64);
    translate([58.8, -1, -0.3]) cube([2.4, 2.2, 1.6]);
    // J6: NMJ6HCD2
    translate([80, -1, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11.4, h = wall + 2, $fn = 64);
    // J7: NMJ6HCD2
    translate([102, -1, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11.4, h = wall + 2, $fn = 64);
    // RV3: RK09L
    translate([122, -1, 6.5]) rotate([-90, 0, 0]) cylinder(d = 9.5, h = wall + 2, $fn = 64);
    translate([120.8, -1, -0.3]) cube([2.4, 2.2, 1.6]);
    // J8: NMJ6HCD2
    translate([142, -1, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11.4, h = wall + 2, $fn = 64);
    // SW1: PTS645
    translate([161, -1, 4.05]) rotate([-90, 0, 0]) cylinder(d = 4.5, h = wall + 2, $fn = 64);
    // the Pi's USB 2 pair: 2.28 mm into the panel
    translate([170.25, -1.00, -14.40]) cube([15.50, 5.00, 18.35]);
    // the Pi's USB 3 pair: 2.50 mm into the panel
    translate([188.25, -1.00, -14.40]) cube([15.50, 5.00, 18.52]);
    // the Pi's Ethernet: 2.55 mm into the panel
    translate([206.28, -1.00, -14.40]) cube([16.94, 5.00, 15.63]);
}

// Everything cut out of the side wall beside the Pi (which fills x_right < x < x_right + wall).
module side_cuts() {
    // USB-C power: the socket's face is 0.80 mm inside the wall's inner face
    translate([226.00, -81.05, -15.19]) cube([5.00, 13.50, 7.50]);
    // both micro-HDMI sockets: faces 0.37 mm inside the wall's inner face
    translate([226.00, -65.95, -15.95]) cube([5.00, 25.90, 9.00]);
}

// Everything cut out of the floor (which fills z_floor - floor_t < z < z_floor).
module floor_cuts() {
    // the SD card's finger opening: the card comes out toward the front, label side down
    hull() for (x = [191.00, 203.00]) for (y = [-103.50, -75.50])
        translate([x, y, z_floor - floor_t - 1]) cylinder(r = 4, h = floor_t + 2, $fn = 32);
    // M2.5 screws from below into the Pi's stand-offs and nuts, heads sunk 1.5 mm
    for (p = pi_holes) translate([p[0], p[1], z_floor - floor_t - 1]) {
        cylinder(d = 2.9, h = floor_t + 20, $fn = 24);
        cylinder(d = 5.4, h = 2.5, $fn = 24);
    }
}

// What the Pi stands on: four bosses under its mounting holes.
module pi_bosses() {
    // (solid: floor_cuts() drills the screw holes through floor and boss together)
    for (p = pi_holes) translate([p[0], p[1], z_floor - 0.5]) cylinder(d = 6, h = 4.0 + 0.5, $fn = 32);
}

// What the board stands on away from the Pi: four bosses under its M3 holes, each with a
// 2.5 mm pilot hole for a self-tapping M3 screw (or drilled out for a heat-set insert).
module board_bosses() {
    for (p = board_holes) translate([p[0], p[1], z_floor - 0.5]) difference() {
        cylinder(d1 = 10, d2 = 7, h = -pcb - z_floor + 0.5, $fn = 32);
        translate([0, 0, -pcb - z_floor - 8.5]) cylinder(d = 2.5, h = 10, $fn = 24);
    }
}

// Simple models of the parts the audio box's fit check needs and KiCad has no 3D model for:
// the Raspberry Pi 5, the screen and the rear-panel jacks and pots. Boxes and cylinders sized
// from the makers' drawings and 3D models (sources in ../plan.md); good for clash checks, not
// for looks.
//
// The jacks and pots: origin on the part's axis at the panel's inner face, on the board's top
// surface; the axis points out of the case along +y.

// Neutrik NMJ6HCD2, 1/4" jack (drawing ST-NMJ6HCD2): body 18.2 wide, 20.61 deep and 15.67 tall
// over the board; axis 8.14 mm up; bushing about 11 mm, 3 mm past the body.
module nmj6hcd2() {
    translate([-9.1, -20.61, 0]) cube([18.2, 20.61, 15.67]);
    translate([0, 0, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11, h = 3, $fn = 48);
}

// Alps RK09L12B0, dual pot, horizontal (Alps catalog): body 10.7 wide and 12.4 deep, shaft
// 6.5 mm up, M9 bushing 5 mm and a 6 mm shaft 15 mm from the mounting surface. The body is
// 4.85 mm above the shaft's axis and reaches down to the board.
module rk09l_dual() {
    translate([-5.35, -12.4, 0]) cube([10.7, 12.4, 11.35]);
    translate([0, 0, 6.5]) rotate([-90, 0, 0]) {
        cylinder(d = 9, h = 5, $fn = 48);
        cylinder(d = 6, h = 15, $fn = 32);
    }
}

// Raspberry Pi 5, in its own frame: x along the long edge from the SD-card end, y from the edge
// with the USB-C and micro-HDMI ports, z = 0 the board's top. Every box is the bounding box of
// that part in Raspberry Pi's own 3D model (STEP, pcb/references/raspberry-pi/pi5-step). The
// Active Cooler is not in that model: 63.5 x 42.5 x 13.7 from its product brief, where it sits
// from the measured 3-4 mm to the GPIO pins; its extent along the board is unverified.
module pi5(cooler = true) {
    color("darkgreen") translate([0, 0, -1.3]) cube([85, 56, 1.3]);
    color("black") {
        translate([7.1, 49.96, 0]) cube([50.8, 5.08, 2.54]);  // GPIO header plastic
        for (x = [8.37 : 2.54 : 56.7]) for (y = [51.23, 53.77])
            translate([x - 0.32, y - 0.32, 0]) cube([0.64, 0.64, 8.5]);  // its pins
        translate([65.3, 49, 0]) cube([2.9, 6, 4]);  // fan connector
        translate([1.1, 23.14, 0]) cube([3.06, 13.71, 3.98]);  // PCIe connector
        for (x = [47.1, 53.3]) translate([x, 0.14, 0]) cube([3.06, 16.71, 3.98]);  // CAM/DISP 0 and 1
    }
    color("silver") {
        translate([70.33, 39.75, 0]) cube([17.45, 14.5, 16.05]);  // USB 2 pair
        translate([70.47, 21.75, 0]) cube([17.53, 14.5, 16.22]);  // USB 3 pair
        translate([66.45, 2.28, 0]) cube([21.6, 15.94, 13.33]);  // Ethernet
        translate([6.73, -1.2, -0.97]) cube([8.94, 7.32, 4.26]);  // USB-C
        for (x = [22.2, 35.6]) translate([x, -1.63, -1.07]) cube([7.2, 8.5, 4.44]);  // micro-HDMI
        translate([2.25, 22.11, -1.3 - 1.42]) cube([11.4, 11.95, 1.42]);  // microSD slot, underneath
    }
    color("orange") translate([-2, 22.6, -1.3 - 1.2]) cube([15, 11, 1]);  // microSD card, 2 mm out
    if (cooler) color("gray") translate([1.3, 5, 0]) cube([63.5, 42.5, 13.7]);
}

// Waveshare 10.1" DSI LCD (C), from Waveshare's own 3D model (STEP). Its frame here: x along
// the short side (147 mm), y along the long side (239 mm), z = 0 the BACK of the glass, the
// viewer toward +z. Behind the glass: the LCD (143 x 228.6 mm, 4.7 mm deep), the driver board
// (76 x 110 mm, its back face 6.3 mm deep, parts on it to 14.8 mm), four M3 threaded
// stand-offs for the case 95 x 68 mm apart (end faces 7.8 mm deep, thread 2.8 mm deep) and
// four M2.5 stand-offs for a Pi (to 14.0 mm deep, not used).
module screen() {
    color("dimgray") translate([-71.5, -117.08, -4.7]) cube([143, 228.6, 4.7]);  // LCD
    color("darkgreen") translate([-38, -58, -6.3]) cube([76, 110, 1.6]);  // driver board
    color("silver") {
        for (x = [-34, 34]) for (y = [-47.5, 47.5]) translate([x, y, -7.8]) cylinder(d = 5.5, h = 1.5, $fn = 24);
        for (x = [-24.5, 24.5]) for (y = [-19, 39]) translate([x, y, -14]) cylinder(d = 5.5, h = 7.7, $fn = 24);
    }
    // the tall parts on the driver board (connectors, switch), as the boxes the model's
    // sections show: all inside x -38..36, y -22..52
    color("black") {
        translate([-37.8, 2.4, -14.8]) cube([8, 30.2, 8.5]);
        translate([-27.25, 30, -14.3]) cube([5.5, 11.75, 8]);
        translate([10, 39.3, -12.9]) cube([17, 12.2, 6.6]);
        translate([20, 30, -14.3]) cube([9, 9.3, 8]);
    }
    color("black", 0.6) translate([-73.5, -119.5, 0]) cube([147, 239, 1.1]);  // glass (drawn last: see-through)
}

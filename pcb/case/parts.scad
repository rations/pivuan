// Simple models of the parts the pedalboard's fit check needs and KiCad has no 3D model for:
// the Raspberry Pi 5 and the rear-panel jacks and pots. Boxes and cylinders sized from the
// makers' drawings (sources in ../plan.md); good for clash checks, not for looks.
//
// The jacks and pots: origin on the part's axis at the panel's inner face, on the board's top
// surface; the axis points out of the case along +y.

// Neutrik NMJ6HCD2, 1/4" jack (drawing ST-NMJ6HCD2 [S96]): body 18.2 wide, 20.61 deep and
// 15.67 tall over the board; axis 8.14 mm up; bushing about 11 mm, 3 mm past the body.
module nmj6hcd2() {
    translate([-9.1, -20.61, 0]) cube([18.2, 20.61, 15.67]);
    translate([0, 0, 8.14]) rotate([-90, 0, 0]) cylinder(d = 11, h = 3, $fn = 48);
}

// Alps RK09L12B0, dual pot, horizontal (Alps catalog [S95]): body 10.7 wide and 12.4 deep,
// shaft 6.5 mm up, M9 bushing 5 mm and a 6 mm shaft 15 mm from the mounting surface. The body's
// height isn't dimensioned: 12 mm here.
module rk09l_dual() {
    translate([-5.35, -12.4, 0]) cube([10.7, 12.4, 12]);
    translate([0, 0, 6.5]) rotate([-90, 0, 0]) {
        cylinder(d = 9, h = 5, $fn = 48);
        cylinder(d = 6, h = 15, $fn = 32);
    }
}

// Same Sky SJ1-3543, 3.5 mm jack (SJ1-354X [S91]): body 12 wide, 11.6 deep, 9.6 tall; M6
// bushing 3.6 mm long; axis about 5.2 mm up (scaled from the drawing).
module sj1_3543() {
    translate([-6, -11.6, 0]) cube([12, 11.6, 9.6]);
    translate([0, 0, 5.2]) rotate([-90, 0, 0]) cylinder(d = 6, h = 3.6, $fn = 32);
}

// Raspberry Pi 5 (mechanical drawing [S49]), in its own frame: x along the long edge from the
// SD-card end, y from the edge with the USB-C and micro-HDMI ports, z = 0 the board's top.
// Port and connector sizes are approximate (scaled from the drawing). The Active Cooler is
// 63.5 x 42.5 x 13.7 [S80]; where it sits is set from the measured 3-4 mm to the GPIO pins,
// its extent along the board is unverified.
module pi5(cooler = true) {
    color("darkgreen") translate([0, 0, -1.6]) cube([85, 56, 1.6]);
    color("black") {
        translate([7.1, 49.9, 0]) cube([50.8, 5.2, 2.5]);  // GPIO header
        translate([66, 49, 0]) cube([2.5, 5, 4]);  // fan connector
        translate([1, 25, 0]) cube([3, 11, 2.5]);  // PCIe connector
        for (x = [47.7, 54.0]) translate([x, 1, 0]) cube([2.6, 15, 4.5]);  // CAM/DISP 0 and 1
    }
    color("silver") {
        translate([70.5, 39.7, 0]) cube([17.6, 14.9, 16]);  // USB 2 pair
        translate([70.5, 21.9, 0]) cube([17.6, 14.1, 16]);  // USB 3 pair
        translate([66.5, 2.1, 0]) cube([21.6, 16.1, 13.5]);  // Ethernet
        translate([11.2 - 4.5, -1.2, 0]) cube([9, 7.5, 3.2]);  // USB-C
        for (x = [25.8, 39.2]) translate([x - 3.3, -1, 0]) cube([6.6, 7.5, 3.4]);  // micro-HDMI
    }
    color("orange") translate([-2, 22.5, -1.6 - 1.2]) cube([15, 11, 1]);  // microSD card, 2 mm out
    if (cooler) color("gray") translate([1.3, 5, 0]) cube([63.5, 42.5, 13.7]);
}

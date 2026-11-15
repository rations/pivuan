// Test print of the case corner the Pi 5 sits in: the floor with its four bosses and the
// SD card's finger opening, the rear wall with the USB and Ethernet openings, the side wall
// with the USB-C and micro-HDMI openings. Written by pcb/gen/panel.py; don't edit by hand.
// Print it floor down. Screw the Pi on (M2.5 from below) and try: every plug you use, with
// the plug pushed fully home; the SD card out and in through the floor with a fingertip.
// The Pi goes in tilted, sockets first into the rear wall, then down onto the bosses.
include <dims.scad>

module pi_corner_test() {
    difference() {
        union() {
            translate([168.50, -113.50, -20.90]) cube([61.50, 116.50, 3.00]);
            translate([168.50, 0.00, -20.90]) cube([61.50, 3.00, 28.52]);
            translate([227.00, -113.50, -20.90]) cube([3.00, 116.50, 20.17]);
            pi_bosses();
        }
        rear_cuts();
        side_cuts();
        floor_cuts();
    }
}

pi_corner_test();

// Case of the Pivuan audio box: a 30 degree wedge for the floor or a desk, with the 10.1"
// screen in its sloping top, the jacks, knobs and the Pi's USB and Ethernet sockets through
// the rear panel, the Pi's USB-C power and micro-HDMI sockets through the right side wall
// (seen from the front), and the SD card reached through a finger opening in the floor.
//
// First version, for the 3D check (fit-check.scad) and for test prints. Print the two test
// pieces (rear-panel-test.scad, pi-corner-test.scad) before any of this.
//
// Frame and the board's and Pi's sizes: dims.scad (written by pcb/gen/panel.py).
// Screen sizes: Waveshare's own 3D model of the 10.1" DSI LCD (C), see parts.scad.
//
// Parts (set `part` below, or call the modules):
//   base()        floor, side walls, front wall, bosses for the Pi and the board
//   rear_panel()  slides on over the jacks, pots and sockets once the board is in; the jack
//                 and pot nuts hold the board to it, 6 screws hold it to the base and the top
//   top()         the sloping panel; the screen's glass lies in a recess, flush
//   tab()         x 4: clamp the screen from behind, one M3 x 6 screw each into the screen's
//                 own threaded stand-offs
//
// Screws: M2.5 x 12 from below through the floor into the Pi's stand-offs (2, by the header:
// 11 mm female-female stand-offs carry the board) and into nuts (2, on the Pi); M3
// self-tapping x 8 into every 2.5 mm pilot hole; M3 x 6 machine screws for the tabs. A screw
// may go no deeper than 2.8 mm into the screen's stand-offs: that is all the thread they have.
include <dims.scad>
use <parts.scad>

part = "all";  // "all", "base", "rear", "top", "tab"

angle = 30;
glass = [147, 239, 1.1];  // the screen's glass: up the slope, across, thick
lcd_y = [-117.08, 111.52];  // the LCD behind it, across (in the screen's own frame); 143 mm up the slope
margin = 12;  // top panel beyond the glass, up and down the slope
side_margin = 4;  // and at each side: the case is 239 + 8 = 247 mm wide
front_h = 20;  // outer height of the front edge: 8 mm stay clear between the screen's deepest
// part and the board's tallest part (the screen power socket) at 20; panel.py's check
top_t = 3;
recess = 1.2;  // the glass lies this deep: flush, 0.1 mm under
screen_flip = false;  // true turns the screen half a turn in its opening (its DSI socket's side)

inner_w = glass[1] + 2 * side_margin - 2 * wall;
x_left = x_right - inner_w;  // the inner face of the side wall at the guitar end
xc = (x_left + x_right) / 2;
z_bot = z_floor - floor_t;
slope = glass[0] + 2 * margin;
run = slope * cos(angle);
rise = slope * sin(angle);
y_front = wall - run;  // the front edge, outside
z_front = z_bot + front_h;  // the top's outer surface at the front edge
z_rear = z_front + rise;  // and at the rear
function z_out(y) = z_front + (y - y_front) * tan(angle);
function z_in(y) = z_out(y) - top_t / cos(angle);  // the top's underside

rear_screws = [[x_left + 4, 25], [x_left + 4, 65], [x_right - 4, 25], [x_right - 4, 65]];  // x, z
top_blocks = [xc - 85, xc + 85];  // x of the top's two blocks the rear panel screws into
front_posts = [x_left + 4, xc, x_right - 4];  // x of the posts the top's front edge screws to
post_y = y_front + 5;

$fn = 48;

// A polygon drawn in (y, z), made solid from x0 to x1.
module along_x(x0, x1) {
    translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(x1 - x0) children();
}

// The space under the top's underside, between the front edge and the rear panel's inner face.
module inside_profile(y0 = y_front, y1 = 0) {
    polygon([[y0, z_bot], [y1, z_bot], [y1, z_in(y1)], [y0, z_in(y0)]]);
}

// Slope frame: x across from the case's middle, y up the slope from its middle, z = 0 the
// top's outer surface, outward.
module slope_place() {
    translate([xc, wall - run / 2, z_front + rise / 2]) rotate([angle, 0, 0]) children();
}

// The screen's own frame (parts.scad: x up or down the slope, y across, z = 0 the glass's back).
module screen_place() {
    slope_place() translate([0, 0, -recess]) rotate([0, 0, screen_flip ? 90 : -90]) children();
}

// A block on a side wall's inner face with a sloping underside, so it prints without support.
// At x (the wall's face), reaching dx into the case (negative: toward lower x).
module corbel(x, dx, z) {
    hull() {
        translate([min(x, x + dx) - 0.5, -8, z]) cube([abs(dx) + 1, 8, 10]);
        translate([x - 0.5, -8, z - abs(dx)]) cube([1, 8, 0.01]);
    }
}

module base() {
    difference() {
        union() {
            // floor
            translate([x_left - wall, y_front, z_bot]) cube([inner_w + 2 * wall, -y_front, floor_t]);
            // side walls and front wall
            along_x(x_left - wall, x_left) inside_profile();
            along_x(x_right, x_right + wall) inside_profile();
            along_x(x_left - wall, x_right + wall) inside_profile(y_front, y_front + wall);
            // posts for the top's front screws, and blocks for the rear panel's screws
            intersection() {
                union() for (x = front_posts) translate([x, post_y, z_bot + 0.5]) cylinder(d = 9, h = 200);
                along_x(x_left - wall, x_right + wall) inside_profile();
            }
            for (s = rear_screws)
                corbel(s[0] < xc ? x_left : x_right, s[0] < xc ? 8 : -8, s[1] - 5);
            pi_bosses();
            board_bosses();
        }
        floor_cuts();
        side_cuts();
        // pilot holes: top's front screws (down into the posts), rear panel's screws (into the blocks)
        for (x = front_posts) translate([x, post_y, z_in(post_y) - 10]) cylinder(d = 2.5, h = 20);
        for (s = rear_screws) translate([s[0], -8, s[1]]) rotate([-90, 0, 0]) cylinder(d = 2.5, h = 9);
        // air for the Pi's cooler: slots in the side wall above the HDMI sockets
        for (y = [-78 : 6 : -18]) translate([x_right - 1, y, -2]) cube([wall + 2, 3, 18]);
        // stick-on feet, 12.7 mm
        for (x = [x_left + 12, x_right - 12]) for (y = [y_front + 14, -14])
            translate([x, y, z_bot - 0.01]) cylinder(d = 13.5, h = 1);
    }
}

module rear_panel() {
    difference() {
        along_x(x_left - wall, x_right + wall) polygon([[0, z_bot], [wall, z_bot], [wall, z_in(wall)], [0, z_in(0)]]);
        rear_cuts();
        for (s = rear_screws) translate([s[0], -1, s[1]]) rotate([-90, 0, 0]) cylinder(d = 3.4, h = wall + 2);
        for (x = top_blocks) translate([x, -1, z_in(-4) - 7]) rotate([-90, 0, 0]) cylinder(d = 3.4, h = wall + 2);
        // air out: slots above the Pi's sockets
        for (x = [174 : 6 : 216]) translate([x, -1, 12]) cube([3, wall + 2, 28]);
    }
}

module top() {
    difference() {
        union() {
            along_x(x_left - wall, x_right + wall)
                polygon([[y_front, z_out(y_front)], [wall, z_out(wall)], [wall, z_in(wall)], [y_front, z_in(y_front)]]);
            // blocks under the rear edge for the rear panel's two top screws
            for (x = top_blocks) intersection() {
                translate([x - 6, -8, z_in(-8) - 14]) cube([12, 8, 30]);
                along_x(x - 7, x + 7) polygon([[-9, z_bot], [1, z_bot], [1, z_in(1) + 0.5], [-9, z_in(-9) + 0.5]]);
            }
        }
        // the glass's recess and the LCD's opening
        slope_place() {
            translate([-glass[1] / 2 - 0.3, -glass[0] / 2 - 0.3, -recess]) cube([glass[1] + 0.6, glass[0] + 0.6, recess + 1]);
            translate([(screen_flip ? -lcd_y[1] : lcd_y[0]) - 0.5, -72, -top_t - 1])
                cube([lcd_y[1] - lcd_y[0] + 1, 144, top_t + 2]);
        }
        for (x = top_blocks) translate([x, -9, z_in(-4) - 7]) rotate([-90, 0, 0]) cylinder(d = 2.5, h = 10);
        // front screws: straight down, heads sunk to a flat seat
        for (x = front_posts) translate([x, post_y, 0]) {
            translate([0, 0, z_in(post_y) - 1]) cylinder(d = 3.4, h = 20);
            translate([0, 0, z_out(post_y) - 1.2]) cylinder(d = 6.5, h = 20);
        }
    }
}

// One screen clamp, in the screen's frame, for the stand-off at (34, 47.5): a bar from the
// stand-off's end face (7.8 mm behind the glass's back) out past the LCD's edge, with a foot
// that presses on the top's underside (1.8 mm behind the glass's back). The foot is 0.2 mm
// taller than the step, so tightening the screw pulls the glass down onto its seat.
module tab() {
    bar = 3.4;
    difference() {
        union() {
            translate([29.5, 43, -7.8 - bar]) cube([51, 9, bar]);
            translate([73, 43, -7.8 - 0.01]) cube([7.5, 9, 7.8 - (top_t - recess) + 0.2]);
        }
        translate([34, 47.5, -20]) cylinder(d = 3.4, h = 30);
    }
}

module tabs() {
    screen_place() for (mx = [0, 1]) for (my = [0, 1]) mirror([mx, 0, 0]) mirror([0, my, 0]) tab();
}

if (part == "all") { base(); rear_panel(); top(); tabs(); }
if (part == "base") base();
if (part == "rear") rear_panel();
if (part == "top") top();
if (part == "tab") tab();

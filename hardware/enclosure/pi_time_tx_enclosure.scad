// Enclosure for the Pi 60 kHz time-signal transmitter
//   Raspberry Pi Zero (W/2W) + Pi 60kHz Time TX pHAT v1.2 + 3 x 9x180 mm ferrite rod antenna
//
// Export one part at a time by setting PART:
//   "base"     printable base
//   "lid"      printable lid (already flipped for printing)
//   "assembly" coloured preview with the Pi, pHAT and antenna in place
//   "exploded" coloured exploded view
//   "stack_exploded" / "stack_assembled"  close-up of fitting the pHAT to the Pi
//   "full_exploded"  every part, spread out in assembly order
//   "check_hit_base" / "check_hit_lid"  collision tests (should render empty)
PART = "assembly";

$fn = 48;

// ---------------- main dimensions (mm) ----------------
wall   = 2.2;        // side walls
floor_t = 2.0;       // base floor
lid_t  = 2.0;        // lid plate
L_in   = 190;        // inside length  (rods are 180 mm)
W_in   = 66;         // inside depth (leaves a 3 mm gap behind the saddles for the cable ties)
H_in   = 32;         // inside height (floor top to lid underside)
L_out  = L_in + 2 * wall;
W_out  = W_in + 2 * wall;
H_base = floor_t + H_in;
fit    = 0.3;        // clearance between lid lip and walls

// ---------------- Pi Zero + pHAT placement ----------------
pi_L = 65; pi_W = 30; pcb_t = 1.6;
pi_x0 = 7.0;                         // gap to left wall (room for the microSD card; clears the corner boss)
pi_y0 = 1.0;                         // port edge 1 mm from the front wall
standoff_h = 5.0;                    // Pi underside height above the floor
pi_z = standoff_h;                   // Pi PCB bottom
stack = 11.0;                        // Pi PCB top to pHAT PCB bottom (M2.5 x 11 spacers)
hat_z = pi_z + pcb_t + stack;        // pHAT PCB bottom
holes = [[3.5, 3.5], [61.5, 3.5], [3.5, 26.5], [61.5, 26.5]];

// Pi Zero port centres, measured from the Pi's left edge (port edge = front)
hdmi_x = 12.4; usb_x = 41.4; pwr_x = 54.0;
port_zc = pi_z + pcb_t + 1.6;        // connector centre height
sd_yc = 16.9;                        // microSD centre from the port edge

// ---------------- antenna ----------------
rod_d = 9; rod_L = 180;
ant_yc = W_in - 16;                  // bundle centre line (along the back wall)
ant_zc = 16;                         // bundle centre height
ant_x0 = (L_in - rod_L) / 2;
saddle_x = [22, 62, 128, 168];       // keep clear of the winding at the centre
cradle_r = 10.8;                     // fits the taped 3-rod bundle (~19-20 mm across)

// ---------------- lid screws ----------------
boss_r = 3.6;                        // slim enough that the Pi stack and antenna drop straight in
boss_in = boss_r - 1.5;              // centres sit so the bosses merge into the corner walls
boss_pts = [[boss_in, boss_in], [L_in - boss_in, boss_in],
            [boss_in, W_in - boss_in], [L_in - boss_in, W_in - boss_in]];
boss_z0 = 22;                        // hanging bosses start above the pHAT
pilot_d = 2.5;                       // M3 self-tapping screw pilot
screw_d = 3.4;

// ======================================================
module rounded_box(l, w, h, r) {
    hull() for (x = [r, l - r], y = [r, w - r]) translate([x, y, 0]) cylinder(r = r, h = h);
}

module base() {
    difference() {
        union() {
            // shell
            difference() {
                translate([-wall, -wall, -floor_t]) rounded_box(L_out, W_out, H_base, 3);
                translate([0, 0, 0]) cube([L_in, W_in, H_in + 1]);
            }
            // Pi standoffs
            for (h = holes) translate([pi_x0 + h[0], pi_y0 + h[1], -0.01])
                cylinder(d = 6, h = standoff_h);
            // antenna saddles
            for (x = saddle_x) translate([x - 4, ant_yc - 13, -0.01]) saddle();
            // hanging lid-screw bosses (45 degree cone underneath, prints without support)
            for (p = boss_pts) translate([p[0], p[1], 0]) {
                translate([0, 0, boss_z0]) cylinder(r = boss_r, h = H_in - boss_z0);
            }
            // sloped support from the corner wall up to each boss (about 45 degrees)
            for (p = boss_pts) hull() {
                translate([p[0], p[1], boss_z0]) cylinder(r = boss_r, h = 0.5);
                translate([p[0] < L_in / 2 ? -0.4 : L_in + 0.4, p[1] < W_in / 2 ? -0.4 : W_in + 0.4, boss_z0 - 10])
                    cylinder(r = 0.6, h = 0.5);
            }
        }
        // standoff pilot holes for M2.5 male thread
        for (h = holes) translate([pi_x0 + h[0], pi_y0 + h[1], -1])
            cylinder(d = 2.2, h = standoff_h + 2);
        // lid screw pilots
        for (p = boss_pts) translate([p[0], p[1], H_in - 10]) cylinder(d = pilot_d, h = 11);
        // front wall: mini-HDMI and the two micro-USB ports (one shared slot)
        translate([pi_x0 + hdmi_x - 7, -wall - 1, port_zc - 4.5]) cube([14, wall + 2, 9]);
        translate([pi_x0 + usb_x - 6.5, -wall - 1, port_zc - 4.5]) cube([pwr_x - usb_x + 13, wall + 2, 9]);
        // left wall: microSD access
        translate([-wall - 1, pi_y0 + sd_yc - 7, pi_z - 1.5]) cube([wall + 2, 14, 5.5]);
        // label on the floor underside
        translate([L_out / 2 - wall, W_out / 2 - wall, -floor_t - 0.01])
            mirror([1, 0, 0]) linear_extrude(0.6)
                text("Pi 60kHz Time TX", size = 7, halign = "center", valign = "center");
    }
}

module saddle() {
    difference() {
        cube([8, 26, ant_zc]);
        translate([-1, 13, ant_zc]) rotate([0, 90, 0]) cylinder(r = cradle_r, h = 10);
        // zip-tie tunnel under the cradle
        translate([1.5, -1, 1.5]) cube([5, 28, 2.6]);
    }
}

module lid() {
    difference() {
        union() {
            translate([-wall, -wall, 0]) rounded_box(L_out, W_out, lid_t, 3);
            // locating lip that drops inside the walls
            difference() {
                translate([fit, fit, -3]) cube([L_in - 2 * fit, W_in - 2 * fit, 3]);
                translate([fit + 1.2, fit + 1.2, -4]) cube([L_in - 2 * fit - 2.4, W_in - 2 * fit - 2.4, 5]);
                for (p = boss_pts) translate([p[0], p[1], -5]) cylinder(r = boss_r + 0.6, h = 6);
            }
        }
        // countersunk M3 holes
        for (p = boss_pts) translate([p[0], p[1], -1]) {
            cylinder(d = screw_d, h = lid_t + 2);
            translate([0, 0, lid_t + 1 - 1.7]) cylinder(d1 = screw_d, d2 = 6.4, h = 1.71);
        }
        // vents over the Pi
        for (i = [0 : 8]) translate([pi_x0 + 10 + i * 5.5, pi_y0 + 6, -1]) cube([2.2, 20, lid_t + 2]);
        // engraved labels
        translate([L_in * 0.62, W_in - 12, lid_t - 0.6]) linear_extrude(1)
            text("60 kHz TIME TX", size = 6, halign = "center", valign = "center");
        translate([L_in * 0.62, W_in - 24, lid_t - 0.6]) linear_extrude(1)
            text("keep clocks parallel to this long side", size = 3.5, halign = "center", valign = "center");
    }
}

// ---------------- reference models (not printed) ----------------
module pi_zero() {
    color("#1e7b3a") difference() {
        rounded_box(pi_L, pi_W, pcb_t, 3);
        for (h = holes) translate([h[0], h[1], -1]) cylinder(d = 2.75, h = 4);
    }
    color("silver") {
        translate([hdmi_x - 5.6, -0.5, pcb_t]) cube([11.2, 7.5, 3.2]);
        translate([usb_x - 4, -0.5, pcb_t]) cube([8, 5.6, 2.6]);
        translate([pwr_x - 4, -0.5, pcb_t]) cube([8, 5.6, 2.6]);
        translate([-1.5, sd_yc - 6, pcb_t]) cube([13, 12, 1.4]);
    }
    color("#222") translate([7.1, pi_W - 5, pcb_t]) cube([50.8, 5, 2.5]);       // male header plastic
    color("#333") translate([25, 8, pcb_t]) cube([12, 12, 1.2]);                // SoC
}

module phat() {
    color("#1e7b3a") difference() {
        rounded_box(pi_L, pi_W, pcb_t, 3);
        for (h = holes) translate([h[0], h[1], -1]) cylinder(d = 2.75, h = 4);
    }
    color("#111") translate([7.1, pi_W - 5, -8.5]) cube([50.8, 5, 8.5]);          // 40-pin socket
    // screw terminal J2: pHAT layout coords (x, y-from-header-edge) 50.35..60.25 x 9.4..19.7
    color("#2a8c4a") translate([50.35, pi_W - 19.7, pcb_t]) cube([9.9, 10.3, 10]);
    color("#222") translate([23, pi_W - 13, pcb_t]) cube([3, 2, 1.1]);            // Q1
    color("#c9a26b") for (i = [0, 1]) translate([31.2 + i * 3.6, pi_W - 18.1, pcb_t]) cube([1.6, 3.2, 1.2]);
    color("#222") translate([22.4, pi_W - 20.8, pcb_t]) cube([3.2, 1.6, 0.6]);    // R1
}

module antenna() {
    // three rods in a triangle, with tape and the 55-turn winding at the centre
    for (o = [[-4.5, -2.6], [4.5, -2.6], [0, 5.2]])
        color("#3a3a3a") translate([0, o[0], o[1]]) rotate([0, 90, 0]) cylinder(d = rod_d, h = rod_L);
    color("#b8520a") translate([rod_L / 2 - 7.5, 0, 0]) rotate([0, 90, 0]) cylinder(d = 21, h = 15);
}

module contents(dz = 0) {
    translate([pi_x0, pi_y0, pi_z + dz]) pi_zero();
    translate([pi_x0, pi_y0, hat_z + dz * 1.6]) phat();
    for (h = holes) color("gold") translate([pi_x0 + h[0], pi_y0 + h[1], pi_z + pcb_t + dz])
        cylinder(d = 5, h = stack, $fn = 6);
    translate([ant_x0, ant_yc, ant_zc - 1.3 + dz * 0.6]) antenna();
}


// ---- close-up of the Pi / standoff / pHAT stack (for the assembly guide) ----
module header_pins() {
    color("gold") for (i = [0:19], j = [0, 1])
        translate([7.1 + 1.27 + i * 2.54 - 0.32, pi_W - 2.5 + (j - 0.5) * 2.54 - 0.32, pcb_t])
            cube([0.64, 0.64, 2.5 + 6]);
}
module standoff() {               // M2.5 x 11 male-female hex standoff
    color("gold") {
        cylinder(d = 5, h = stack, $fn = 6);
        translate([0, 0, -6]) cylinder(d = 2.4, h = 6, $fn = 16);
    }
}
module m25_screw() {
    color("#b0b0b0") {
        cylinder(d = 4.5, h = 1.8);
        translate([0, 0, -5]) cylinder(d = 2.4, h = 5, $fn = 16);
    }
}
module base_corner() {            // just the floor and posts under the Pi
    color("#d8d8d2") {
        translate([-4, -4, -floor_t]) cube([pi_L + 8, pi_W + 8, floor_t]);
        for (h = holes) translate([h[0], h[1], 0]) difference() {
            cylinder(d = 6, h = standoff_h);
            translate([0, 0, 1]) cylinder(d = 2.2, h = standoff_h);
        }
    }
}
module stack_view(e = 0) {        // e = gap added between parts
    base_corner();
    translate([0, 0, pi_z + e]) { pi_zero(); header_pins(); }
    for (h = holes) translate([h[0], h[1], pi_z + pcb_t + 2 * e]) standoff();
    translate([0, 0, hat_z + 3 * e]) phat();
    for (h = holes) translate([h[0], h[1], hat_z + pcb_t + 4 * e]) m25_screw();
}

// ---- exploded view of the whole unit, in assembly order ----
module m3_screw() {               // countersunk M3 x 10 self-tapper
    color("#b0b0b0") {
        translate([0, 0, -1.7]) cylinder(d1 = 3, d2 = 6, h = 1.7);
        translate([0, 0, -10]) cylinder(d = 3, h = 8.3, $fn = 16);
    }
}
module cable_tie() {
    color("#f4f4f0") rotate([0, 90, 0]) difference() {
        cylinder(r = cradle_r + 1.2, h = 2.5, $fn = 64);
        translate([0, 0, -1]) cylinder(r = cradle_r, h = 5, $fn = 64);
    }
}
module full_exploded(e = 22) {
    color("#d8d8d2") base();
    // Pi, standoffs, pHAT and screws (front-left)
    translate([pi_x0, pi_y0, 0]) {
        translate([0, 0, pi_z + e]) { pi_zero(); header_pins(); }
        for (h = holes) translate([h[0], h[1], pi_z + pcb_t + 2 * e]) standoff();
        translate([0, 0, hat_z + 3 * e]) phat();
        for (h = holes) translate([h[0], h[1], hat_z + pcb_t + 4 * e]) m25_screw();
    }
    // antenna and its two cable ties (back wall)
    ant_dy = 1.8 * e;             // pulled back so it doesn't hide the Pi stack
    translate([ant_x0, ant_yc + ant_dy, ant_zc - 1.3 + 1.4 * e]) antenna();
    for (x = [saddle_x[1], saddle_x[2]]) translate([x - 1.25, ant_yc + ant_dy, ant_zc + 2.4 * e]) cable_tie();
    // lid and its screws
    color("#e9e9e4") translate([0, 0, H_in + 5.2 * e]) lid();
    for (p = boss_pts) translate([p[0], p[1], H_in + lid_t + 6.2 * e]) m3_screw();
}

if (PART == "base") base();
else if (PART == "lid") translate([0, W_in, lid_t]) rotate([180, 0, 0]) lid();
else if (PART == "check_contents") contents();
else if (PART == "check_hit_base") intersection() { base(); translate([0, 0, 0.05]) contents(); }
else if (PART == "check_hit_lid") intersection() { translate([0, 0, H_in]) lid(); contents(); }
else if (PART == "check_lid") translate([0, 0, H_in]) lid();
else if (PART == "assembly") {
    color("#d8d8d2") base();
    contents();
    color("#e9e9e4", 0.35) translate([0, 0, H_in]) lid();
}
else if (PART == "stack_exploded") stack_view(14);
else if (PART == "full_exploded") full_exploded();
else if (PART == "stack_assembled") stack_view(0);
else if (PART == "exploded") {
    color("#d8d8d2") base();
    contents(18);
    color("#e9e9e4") translate([0, 0, H_in + 55]) lid();
}

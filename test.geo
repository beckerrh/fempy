p0 = newp;
Point(p0) = {-0.75, -0.8, 0, 0.1};
p1 = newp;
Point(p1) = {-0.1, -0.8, 0, 0.1};
p2 = newp;
Point(p2) = {-0.1, 0.1, 0, 0.1};
p3 = newp;
Point(p3) = {-0.75, 0.1, 0, 0.1};
l0 = newl;
Line(l0) = {p0, p1};
l1 = newl;
Line(l1) = {p1, p2};
l2 = newl;
Line(l2) = {p2, p3};
l3 = newl;
Line(l3) = {p3, p0};
ll0 = newll;
Line Loop(ll0) = {l0, l1, l2, l3};
s0 = news;
Plane Surface(s0) = {ll0};
p4 = newp;
Point(p4) = {-0.425, -0.35, 0.0, 0.5};
Point {p4} In Surface {s0};
Physical Surface(200) = {s0};
p5 = newp;
Point(p5) = {0.75, -0.8, 0, 0.1};
p6 = newp;
Point(p6) = {0.1, -0.8, 0, 0.1};
p7 = newp;
Point(p7) = {0.1, 0.1, 0, 0.1};
p8 = newp;
Point(p8) = {0.75, 0.1, 0, 0.1};
l4 = newl;
Line(l4) = {p5, p6};
l5 = newl;
Line(l5) = {p6, p7};
l6 = newl;
Line(l6) = {p7, p8};
l7 = newl;
Line(l7) = {p8, p5};
ll1 = newll;
Line Loop(ll1) = {l4, l5, l6, l7};
s1 = news;
Plane Surface(s1) = {ll1};
p9 = newp;
Point(p9) = {0.425, -0.35, 0.0, 0.5};
Point {p9} In Surface {s1};
Physical Surface(201) = {s1};
p10 = newp;
Point(p10) = {-1, -1, 0, 0.5};
p11 = newp;
Point(p11) = {1, -1, 0, 0.5};
p12 = newp;
Point(p12) = {1, 1, 0, 0.5};
p13 = newp;
Point(p13) = {-1, 1, 0, 0.5};
l8 = newl;
Line(l8) = {p10, p11};
l9 = newl;
Line(l9) = {p11, p12};
l10 = newl;
Line(l10) = {p12, p13};
l11 = newl;
Line(l11) = {p13, p10};
ll2 = newll;
Line Loop(ll2) = {l8, l9, l10, l11};
s2 = news;
Plane Surface(s2) = {ll2,ll0,ll1};
Physical Line(10) = {l8};
Physical Line(20) = {l9};
Physical Line(30) = {l10};
Physical Line(40) = {l11};
Physical Surface(100) = {s2};
p14 = newp;
Point(p14) = {-0.5, 1, 0, 0.05};
Point {p14} In Surface {s2};
Physical Point(1) = {p14};
p15 = newp;
Point(p15) = {0, 1, 0, 0.05};
Point {p15} In Surface {s2};
Physical Point(2) = {p15};
p16 = newp;
Point(p16) = {-0.5, 1, 0, 0.05};
Point {p16} In Surface {s2};
Physical Point(3) = {p16};
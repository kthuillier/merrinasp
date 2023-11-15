#program base.

1 { x(0..1) } 1.
1 { y(0..1) } 1.
1 { z(0..1) } 1.

&dom(x){0..5}=y.
% &sum(x){5 * y: x(1); -2 * z: x(0)} <= 0.
&sum(x){5 * y} <= 0 :- x(1), not x(0).
&sum(x){-2 * z} <= 0 :- x(0), not x(1).
&assert(x){y} <= 3.

&dom(y){0..5}=y.
&sum(y){y} <= -1 :- y(0).
&sum(y){y} >= 2 :- y(1).

&dom(z){0..5}=y.
&sum(z){3 * y} >= 2 :- z(1).

#show.
#show x/1.
#show y/1.
#show z/1.
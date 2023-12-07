#program base.

1 { x(0..1) } 1.
1 { z(0..1) } 1.

&dom(x){0..5}=y.
&sum(x){5 * y: x(1); -2 * z: x(0)} <= 0.
&assert(x){y} <= 3.
&maximize(x){y}.
&maximize(x){-2 * y}.

&dom(z){0..5}=y.
&sum(z){3 * y} >= 2 :- z(1).
&maximize(z){2 * y} @ 3.
&minimize(z){y} @ 2.

#show.
#show x/1.
#show z/1.
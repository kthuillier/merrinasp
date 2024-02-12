#program base.

1 { x(0..1) } 1.

&dom(x(1)){0..5}=y.
&sum(x(1)){5 * y: x(1); -2 * z: x(0)} <= 0.
&assert(x(1)){y} <= 3.

&dom(x(2)){0..5}=y.
&sum(x(2)){5 * y: x(1); -2 * z: x(0)} <= 0.
&assert(x(2)){y} <= 3.

#show.
#show x/1.
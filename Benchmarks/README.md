# Python-rp-PICO-benchmarks

The main intent is to compare standard pcode with native and viper copilation modes.
Also check some coding method effect on execution speed.

The first example "tstmodulus.py" evaluates the best method to implement
a wraping counter, using the standard: n = (n + 1) % wrap, vs the manual
method:  n += 1; if n == wrap: n = 0.  Interestingly, the fastest method is
not the same on every compilation modes!

for lazy people or... that do not own a pico
tstmodulus.py output
-----------------------------------------------------------
 Time in seconds to execute 1000000 modulus vs add/compare
-----------------------------------------------------------
          Normal         Native         Viper
   + > : 8.556525       3.571998       0.351464
Modulo : 7.456750       3.589137       0.670405
-----------------------------------------------------------

The second example "asm_bigloop.py" Check asm execution speed!!!
Also benchmark the time to call a python function.

Results:
asm loops:  1000000
16081 us :  loops/s = 62185188

Python loops:  1000000
4832443 us :  loops/s = 206934
Not important:  25

Python calls: 1000000
6373625 us :  calls/s = 156896

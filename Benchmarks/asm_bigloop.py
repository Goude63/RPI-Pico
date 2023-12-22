#
# Author: Marc Pelletier, sept 18, 2023
# Program to benchmark asm code compiled by Micropython
# Compared to similar loop in bytecode/python
#
# Unrelated test: check speed of calling a python function
#

import time, machine

loop_cnt = const(1000000)

@micropython.asm_thumb
def tst():
    align(4)
    mov(r7,pc)
    b(CONT)

    # thumb instructions cannot hold big constants...
    # need pc relative data for big values
    data    (4, loop_cnt)     #  0

    label(CONT)    
    ldr(r2,[r7, 0])
    mov(r1,1)
    mov(r0,0)
    label(loop)
    add(r0,r0,r1)
    sub(r2,r2,r1)
    bne(loop)
    
def py_call():
    x = 25
    return(x)

def many():
    for n in range(loop_cnt): y = py_call()
    return(y)

machine.freq(250000000)


t0 = time.ticks_us()
tst()
dt = time.ticks_us() - t0
print("asm loops: ", loop_cnt )
print(dt, end=" us :  loops/s = ")
print(int(loop_cnt/(dt/1000000)))
print()

t0 = time.ticks_us()
n = 0
for i in range(0,loop_cnt): n+= 1
dt = time.ticks_us() - t0
print("Python loops: ", loop_cnt )
print(dt, end=" us :  loops/s = ")
print(int(loop_cnt/(dt/1000000)))

t0 = time.ticks_us()
print('Not important: ', many())
dt = time.ticks_us() - t0
print()
print("Python calls:", loop_cnt)
print(dt, end=" us :  calls/s = ")
print(int(loop_cnt/(dt/1000000)))
#
# Author: Marc Pelletier, sept 18, 2023
# Program to benchmark which method is faster when implementing
# a wraping counter/index. In this test, I wrap after 99 to 0.
# method 1:  n += 1; if n == 100: n = 0
# method 2:  n = (n + 1) % 100
#
# Realizing that modulus operator (%) is an integer division
# and would intuitively take more time 
#
# This test also compares the native and viper versions (PICO)
#
import time

n = 1000000

def pgt(n:int):
    i = 0
    t0 = time.ticks_us()
    for n in range(0,n):
        i += 1
        if (i == 100): i = 1
    dt = time.ticks_us() - t0
    return dt

def mod(n:int):
    i = 0
    t0 = time.ticks_us()
    for n in range(0,n):
        i = (i + 1) % 100
    dt = time.ticks_us() - t0
    return dt

@micropython.native
def pgtn(n:int):
    i = 0
    t0 = time.ticks_us()
    for n in range(0,n):
        i += 1
        if (i == 100): i = 1
    dt = time.ticks_us() - t0
    return dt

@micropython.native 
def modn(n:int):
    i = 0
    t0 = time.ticks_us()
    for n in range(0,n):
        i = (i + 1) % 100
    dt = time.ticks_us() - t0
    return dt

@micropython.viper  # try native and viper!!
def pgtv(n:int):
    i = 0
    t0 = time.ticks_us()
    for n in range(0,n):
        i += 1
        if (i == 100): i = 1
    dt = time.ticks_us() - t0
    return dt

@micropython.viper # try native and viper!!
def modv(n:int):
    i = 0
    t0 = time.ticks_us()
    for n in range(0,n):
        i = (i + 1) % 100
    dt = time.ticks_us() - t0
    return dt

# format n microseconds to seconds with 6 digits
def frmt(n):
    return '{0:1.6f}'.format(n/1000000)

line = 59
print('-' * line)
print(' Time in seconds to execute ' + str(n) + ' modulus vs add/compare')
print('-' * line)
print('          Normal         Native         Viper')
print('   + > : ' + frmt(pgt(n)), end = '       ') 
print(frmt(pgtn(n)), end = '       ') 
print(frmt(pgtv(n))) 

print('Modulo : ' + frmt(mod(n)), end = '       ')
print(frmt(modn(n)), end = '       ') 
print(frmt(modv(n))) 
print('-' * line)
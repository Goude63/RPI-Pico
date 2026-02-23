machine.freq(280_000_000)
from machine import Pin
import time


SLEEP = 5
i = 0
on = True
while True:
	p = Pin(i, Pin.OUT)
	p.value(on)
	time.sleep_ms(SLEEP)
	i += 1
	if i >= 22: 
		i = 0
		on = not on
		time.sleep_ms(30*SLEEP)
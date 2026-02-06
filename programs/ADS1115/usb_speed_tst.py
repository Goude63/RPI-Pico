from machine import Pin
from led import LED
import time

led = LED()
	
@micropython.native
def main():
	machine.freq(250000000)

	n=1
	print('start')
	while(True):
		led.off()
		# 100 bytes (incluant \r\n du print)
		print(f'{n:06d}:0123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890')
		led.on(0,0,44)
		n += 1
main()
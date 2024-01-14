#
#  Record microphone ADC ch 0 to SD Card (Waveshare pico zero)
#  UI: Press button to start/stop recording (red led = record)
#      Long press button to quit. Led off when program ends
#  Also file auto split every hour. Led blue = stand-by/not recording
#  SD Card on SPI0 GP0-GP3, button on GP13 -> gnd 
#  GP26: Mic with DC offset ~1.25V @ ~2.5V pk2pk (on loudest sound)

from adc import Adc
from sdcard import SDCard
from machine import Pin
import time, sys, gc
from utils import *
from led import LED

def Next_fn(i):
	return '/sd/rec' + '{:03.0f}'.format(i) + '.bin'

@micropython.native
def main():
#if True:
	machine.freq(270000000)
	gc.collect()
	led = LED()
	led.off()
	SDCard.Mount()

	# if recordings are there, skip files
	fno = 1
	while exists(Next_fn(fno)): 
		fno += 1

	adc = Adc(chs=0, fs = 44100, buf_size=4096)
	btn_up = Pin(13,Pin.IN,Pin.PULL_UP) # ground GP13 to stop
	gain = Pin(9,Pin.OUT,value=0) # gain option (1: 40db, 0: 50db, float: 60db)

	led.off()
	run = True
	while run:
		led.on(0,0,16) # blue = stand by
		n = 0
		while n < 10 and not btn_up(): # wait btn up
			n += 1
			time.sleep_ms(100)
		while btn_up(): pass		# wait press
		while not btn_up(): # short press = start record
			if n == 10: led.on(5,5,5)   # dim=>quit soon
			n += 1			# long press = quit			
			if n == 20: 
				led.off() # exit: led off
				run = False
				break
			else: time.sleep_ms(100)

		record = run
		r = 16
		while record:
			gc.collect()
			fn = Next_fn(fno)
			f = open(fn, "w")
			adc.WriteFileHdr(f)
			adc.Start(file=f)
			for n in range(3600): # (3600= 1h) 1 hrs per file
				if btn_up():
					led.on(r,0,0) # red blink when recording
					r = 16 - r
					time.sleep(1)
				else:
					record = False
			adc.Stop()
			f.close()
			fno += 1
	SDCard.UMount()

main()

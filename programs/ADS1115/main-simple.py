from ADS1115 import *
from usbcom import USBCOM
from machine import Pin
from led import LED
import time

adc = ADS1115()
usb = USBCOM()
led = LED()
Chnls = (0, 1, 2, 3) 
delay = 2000_000
rng   = 5		# def max range +/-6.144V

def SetFs(fs):
	global delay
	adc.setConvRate(ADS1115_860_SPS)
	hwdt = 1/500 # margin for execution time
	swdt = 1/fs
	delay = swdt * 1000_000  # micro seconds
	cnt = max(1,swdt//hwdt)
	adc.setAvgCNt(cnt)
	print(f'cnt:{cnt}, delay:{delay}')

@micropython.native
def ProcessMessages():
	msg=usb.Scan().lower()
	if not msg: return

	if (msg[0:10]=='set_range='):
		r = int(msg[10:])
		if (0<=r<=5):
			rng = r
			adc.setVoltageRange_mV(ADS1115_RNG[rng])
			print('Range set to ix',rng)

	if (msg[0:7]=='set_fs='):
		r = float(msg[7:])
		if (0.1<=r<=500):
			SetFs(r)
			print('fs set to ',r)
	
def main():
	machine.freq(250000000)
	SetFs(1)	
	adc.setVoltageRange_mV(ADS1115_RNG[rng])
	B = 44;	b = B

	t0 = time.ticks_us()
	while(True):
		led.on(0,0,b)
		b = B - b
		ProcessMessages()
		while time.ticks_diff(time.ticks_us(), t0) < delay:
			ProcessMessages()
		t0 = time.ticks_us()
		m = adc.readMulti(Chnls)
		print("acq=", end="")
		print(m)
main()
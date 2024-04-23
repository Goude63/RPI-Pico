from dma import Dma
from utils import *
import os,gc,time,machine,struct
import array, math, uctypes, random
from machine import PWM, Pin,mem32

# Receives PWM values from main code in 2 bytes/u16 format,
# received in two bytes (LSB,MSB) 
# outputs 4 bytes values to dma2 that send to PWM engine
@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_LEFT)
def pwm_bridge():
	mov(isr,null)
	pull(block)    # retrieve PWM value msb
	in_(osr,8)
	pull(block)    # retrieve PWM value lsb
	in_(osr,8)
	push(block)    # push 16 bits value (in 32 bits output FIFO)

class Alexa:
	USED_PWM_CH = []
	def __init__(self, gpio = 14, fs = 12000, pio_sm=0):
		self.fs = fs
		self.gpio = gpio

		self.PIORX = 0x50200020 + 4 * pio_sm

		# Compile and load state machine bridge
		self.sm = rp2.StateMachine(pio_sm, pwm_bridge) 
		self.sm.active(1)
		
		# setup PWM
		self.pwm_ch = (gpio & 0xF) >> 1 
		if self.pwm_ch in Alexa.USED_PWM_CH: 
			raise(Exception('PWM channe ', self.pwm_ch,' already in use'))
		Alexa.USED_PWM_CH.append(self.pwm_ch)
		self.pwm = PWM(Pin(gpio), freq=fs, duty_u16=32768) # init on center
		self.zero = mem32[0x4005000c + 0x14 * self.pwm_ch] # actual CC value for zero
		self.running = True
		self.PWMTX = 0x4005000c + 0x14 * self.pwm_ch
		self.Off()

		# setup DMA PIO->PWM.  The main code will send using the blocking 'put'
		self.dma = Dma(data_size=4)
		self.dma.SetDREQ(24 + self.pwm_ch)   # DREQ_PWM_WRAP0 = 24
		self.dma.SetAddrInc(0, 0) # From PIO to PWM: no address increment
		self.dma.SetReadadd(self.PIORX)		
		self.dma.SetWriteadd(self.PWMTX) # CHx_CC register		

		#create audio dictionary (*.u16 files)
		self.words = {}
		for f in os.ilistdir():
			x = f[0].find('.u16')
			if x>0:
				self.words[f[0][:x]] = f[0] # filename for each word
		gc.collect()
	
	def Play(self, seq, pause_ms = 150):
		# Do not execute if any word not in dictionnary
		for word in seq:
			if not word in self.words.keys():
				return False
		for word in seq:
			gc.collect()
			with open(self.words[word],'rb') as file:
					wav = file.read()
			self.dma.SetCnt(len(wav)//2) 
			self.dma.Trigger()
			self.sm.put(wav)
			while self.dma.Busy(): pass
			time.sleep_ms(pause_ms)
		self.Off()
		gc.collect()
		return True
	
	def Off(self):
		if self.running:
			self.pwm.duty_u16(65535)
	
	def Stop(self):
		if self.running: 
			self.pwm.duty_u16(0)
			self.pwm.deinit()
			self.running = False
	
	def DeInit(self):
		self.Stop()
		self.__del__()


if __name__ == "__main__":
	mhz, khz = (1000000, 1000)
	machine.freq(256 * mhz)
	alexa = Alexa()
	print('Zero=',alexa.zero)

	alexa.Play(['alexa','off','alex'])


	



import uctypes, array, time
from machine import mem32

def hexn(x, n=32):
	return hex(x & (2**n-1))

class Adc:    
	BASE_ADC  = 0x4004c000
	CS        = BASE_ADC + 0x00
	RESULT    = BASE_ADC + 0x04
	FCS       = BASE_ADC + 0x08
	FIFO      = BASE_ADC + 0x0c
	DIV       = BASE_ADC + 0x10
	INTR      = BASE_ADC + 0x14
	INTE      = BASE_ADC + 0x18
	INTF      = BASE_ADC + 0x1c
	INTS      = BASE_ADC + 0x20

	# create Adc object
	def __init__(self, chs=0, bits = 12, fs=8000, buf_size=64):
		self.fs = fs
		self.t_us = 1000000 // fs
		self.ch_mask = 0
		self.n = 1
		self.bits = bits
		self.buf = array.array('H', [0])
		if type(chs) == type([]):
			self.n = len(chs)
			for ch in chs: 
				if ch<=4: self.ch_mask |= (2 ** ch)
				else: raise(Exception('Invalid ADC channel'))
			self.chs = chs
		else:
			if chs<=4: self.ch_mask = (2 ** chs)
			else: raise(Exception('Invalid ADC channel'))
			self.chs = [chs]

		# select clock
		# if fs<10: raise(Exception('Sampling rate must be at least 10Hz'))
		# div = 48000000 * 256 // fs # lower 8 bits are fractional
		# mem32[Adc.DIV] = div

		# enable adc and, if needed, temperature sensor
		cs = 1
		if self.ch_mask & 0x10: cs |= 2  # if ch4: enable temperature sensor 
		mem32[Adc.CS] = cs 
		while (mem32[Adc.CS] & 0x100) == 0: pass  # wait for ADC to be ready

		# setup ADC for dma transfers
		# cs |= self.ch_mask << 16  # set CS.RROBIN (move to ReadDMA)
		self.cs = cs
	
	# read n times each channel. Buffer must be large enough (No dma)
	@micropython.native
	def Read(self, n=1, buf=None): 
		if buf is None:
			if len(self.buf) != n*self.n: 
				self.buf = array.array('H', [0] * n * self.n)
		else: self.buf = buf

		self.cs &= ~(0x1F << 20) # clear RROBIN for manual read
		mem32[Adc.FCS] &= ~1     # disable FIFO

		ix = 0
		for i in range(0,n):
			for c in self.chs:
				self.cs &= ~(7<<12) # clear current ch value 
				self.cs |= (c<<12) | 4 # set AINSEL and set START_ONCE 
				mem32[Adc.CS] = self.cs  # execute (write to CS register)
				while (mem32[Adc.CS] & 0x100) == 0: pass  # wait conversion done
				self.buf[ix] = mem32[Adc.RESULT]
				ix += 1
			time.sleep_us(self.t_us)
		return self.buf

# Test it.
adc = Adc(chs=4,fs = 2) # test with ch4: temp sensor
print('n=',adc.n, ' mask=', bin(adc.ch_mask), ' chs=', adc.chs)
while True:
	print(adc.Read(5), end=' T=')
	print(27-(3.3*adc.buf[0]/4096 - 0.706)/.001721)
	time.sleep_ms(200)
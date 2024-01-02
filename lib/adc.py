import uctypes, array, time
from machine import mem32

_ADC = None

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
	def __init__(self, chs=0, bits = 12, fs=8000, buf_size=128):
		if not (_ADC is None): raise(Exception('Only instanciate one Adc object please'))

		_ADC = self #TBD set back to None in DeInit()

		self.fs = fs
		self.t_us = 1000000 // fs
		self.ch_mask = 0
		self.n = 1
		self.bits = bits
		self.buf = array.array('H', [0])
		self.buf_size = buf_size
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

	# If file object is present, will write to file. CB(buf) will be called if provided
	@micropython.native
	def Start(self, buf=None, CB=None): 
		if (buf is None) and (CB is None): raise(Exception('"buf" or "CB" required'))
		# prepare ping pong buffers
		self.b1 =  array.array('H', [0] * self.buf_size)
		self.b2 =  array.array('H', [0] * self.buf_size)
		self.dma_chain = Dma()

		# DMA channel used to send wave data
		self.dma_adc = Dma(data_size=4) # acquisition
		self.dma_adc.SetDREQ(36)   # DREQ_ADC = 26
		self.dma_adc.SetAddrInc(0, 1) # No Read increment (adc), write bufferinc 
		self.dma_adc.SetReadadd(Adc.FIFO)		
		self.dma_adc.SetWriteadd(uctypes.addressof(self.b2)) 	
		self.dma_adc.SetCnt(1) # count = 1 for first

		# DMA Channel used to re-trigger dma_adc
		self.dma_chain = Dma(data_size=4) # chain 1 blk to repeat
		self.dma_adc.ChainTo(self.dma_chain.ch) # to retrigger
		self.dma_chain.SetDREQ(0x3f) # no DREQ
		self.dma_chain.SetAddrInc(1, 1) # 2 elements to write: need inc
		self.chain = array.array("L",[uctypes.addressof(self.b1), self.buf_size]) 
		self.bx = 1 # buffer ix filled by dma  
		self.dma_chain.SetReadadd(uctypes.addressof(self.chain))
		self.dma_chain.SetWriteadd(self.dma_adc.TrigCtrlReg + 0xc) # WRITE_ADDR, TRANS_COUNT_TRIF
		self.dma_chain.SetCnt(2)
		self.dma_chain.Enable()

		#setup interrupts

		self.dma_adc.Trigger()

# Test it.
adc = Adc(chs=4,fs = 2) # test with ch4: temp sensor
print('n=',adc.n, ' mask=', bin(adc.ch_mask), ' chs=', adc.chs)
while True:
	print(adc.Read(5), end=' T=')
	print(27-(3.3*adc.buf[0]/4096 - 0.706)/.001721)
	time.sleep_ms(200)
import uctypes, array, time, math
from machine import mem32
from dma import Dma
from utils import *

# Receives adc values from dma1 in 4 bytes format, 
# outputs 2 bytes to dma2 that send to 16 bits buffer
# also generates an interrupts every time buffer size count received
# Must push buffers size (not fom dma) first, then dma1 sends data
@rp2.asm_pio(push_thresh=8, in_shiftdir=rp2.PIO.SHIFT_LEFT, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def adc_bridge():
	pull(block)         # retrieve buffer size (sample count)
	mov(x,osr)          # buffer size stored in x 
	mov(y,x)
	jmp(x_dec,'next')  # we need buffer size -1

	wrap_target()  # loop when buffer size has been reached
	mov(y,x)       # copy buffer size to y

	label('next')  # loop when buffer size not yet reached
	pull(block)    # retrieve adc value in 32 bits format

	out(isr,8)
	push(block)
	out(isr,8)
	push(block)
	jmp(y_dec,'next')  # no irq until 
	irq(0)
	# wrap() # Not needed, program auto wraps on end
	#sample code to setup PIO program
	'''
	sm = rp2.StateMachine(0, adc_bridge) # in_shiftdir=rp2.PIO.SHIFT_RIGHT, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
	x = sm.irq(buf_switch)
	sm.active(1)

	sm.put(4) # buffer size for test
	for n in range(0,12):
		a = ((n*2) + 1) % 16
		b = (a + 1) % 16
		sm.put(a + (b << 8))
		while sm.rx_fifo()>0:
			print(hex(sm.get()), end = ' ')

	#time.sleep_ms(300)
	#sm.active(0)
	'''	

# interrupt routine to copy data
def buf_switch(pio):
    print('(*) ', end ='') # pio.irq().flags(), end =' ')

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

	_ADC = None  # reference to unique instance

	# create Adc object
	def __init__(self, chs=0, bits = 12, fs=8000, buf_size=128):
		if not (Adc._ADC is None): raise(Exception('Only instanciate one Adc object please'))

		Adc._ADC = self #TBD set back to None in DeInit()

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

		self.cs &= ~(0x1F << 16) # clear RROBIN for manual read
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
	#@micropython.native
	def Start(self, buf=None, CB=None, pio_sm=0): 
		bs = self.buf_size
		if (buf is None) and (CB is None): raise(Exception('"buf" or "CB" required'))
		bs_bits = math.log2(bs)		
		if bs_bits != round(bs_bits): raise(Exception('"Buffer Size" must be a power of 2'))
		if pio_sm > 3: raise(Exception('"pio_sm" must be <= 3'))

		PIOTX = 0x50200010 + 4 * pio_sm

		# setup state machine
		self.sm = rp2.StateMachine(pio_sm, adc_bridge) 
		self.irq = self.sm.irq(buf_switch)
		self.sm.active(1)

		# prepare ping pong. 
		# Need 2, but allocate 3 to insure dma wrap alignment is possible
		self.buf =  array.array('H', [0] * (bs * 3))
		s0 = uctypes.addressof(self.buf)

		bs_bits = int(bs_bits)
		mask = int('0b' + ('1' * int(bs_bits)))
		ofst = mask - ((s0 & mask) ^ mask)
		s0 += ofst
		# (buff start, buffer last) for each ping pong buffer
		self.bufs_spec = [(s0, s0+bs-1), (s0 + bs, s0 + 2 * bs - 1)]  

		# DMA channel used to copy adc to dword pio FIFO
		self.dma_adc = Dma(data_size=4) # acquisition
		self.dma_adc.SetDREQ(36)   # DREQ_ADC = 26
		self.dma_adc.SetAddrInc(0, 0) # No increment: adc to PIO FIFO = fixed addresses
		self.dma_adc.SetReadadd(Adc.FIFO)		
		self.dma_adc.SetWriteadd(PIOTX) 	
		self.dma_adc.SetCnt(0xffffffff) # @22Ksps, this is > 54 hours

		# DMA Channel used to copy pio FIFO bytes (2 per sample) to ram
		self.dma_ram = Dma(data_size=1) # chain 1 blk to repeat
		self.dma_ram.SetDREQ(4+pio_sm)  # DREQ_PIO0_RX1 to RX3
		self.dma_ram.SetAddrInc(0, 1)   # always read from PIO, wrapped write
		self.dma_ram.SetReadadd(PIOTX + 0x13) # matching RX is + 0x13 (byte access)
		self.dma_ram.SetWriteadd(s0)      # WRITE_ADDR, TRANS_COUNT_TRIF
		self.dma_ram.SetWrap(bs_bits, 1)  # set wrap bits, and wrap on write 
		self.dma_ram.SetCnt(0xffffffff) # 27hrs at 22ksps

		# setup Adc
		# select clock
		if self.fs<10: raise(Exception('Sampling rate must be at least 10Hz'))
		div = 48000000 * 256 // self.fs # lower 8 bits are fractional
		mem32[Adc.DIV] = div

		self.cs &= ~(0x1F << 16) # clear RROBIN
		self.cs |= self.ch_mask << 16 | 0x8 # set RROBIN and START_MANY
		mem32[Adc.FCS] |= 1      # enable FIFO (needed for dma  access)

		#start dma
		self.dma_adc.Trigger()
		self.dma_ram.Trigger()
		mem32[Adc.CS] = self.cs  # start adc


# Test it.
'''
adc = Adc(chs=4,fs = 2) # test with ch4: temp sensor
print('n=',adc.n, ' mask=', bin(adc.ch_mask), ' chs=', adc.chs)
while True:
	print(adc.Read(5), end=' T=')
	print(27-(3.3*adc.buf[0]/4096 - 0.706)/.001721)
	time.sleep_ms(200)
'''

def DataCB():
	pass

adc = Adc(chs=4,fs = 20,buf_size=16) # test with ch4: temp sensor
adc.Start(CB=DataCB)
adc.dma_adc.Info()



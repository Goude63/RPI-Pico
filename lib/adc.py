import uctypes, array, time, math, rp2
from machine import mem32, mem16
from dma import Dma
from utils import *

import micropython
micropython.alloc_emergency_exception_buf(100)

# Receives adc values from dma1 in 4 bytes format, 
# outputs 2 bytes to dma2 that send to 16 bits buffer
# also generates an interrupts every time buffer size count received
# Must "put" buffers size as first FIFO entry, then dma1 sends data
@rp2.asm_pio(push_thresh=32, in_shiftdir=rp2.PIO.SHIFT_LEFT, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def adc_bridge():
	pull(block)	# retrieve buffer size (sample count)
	mov(x,osr)	# buffer size stored in x 
	mov(y,x)
	pull(block)	# discard first sample (not in RROBIN)
	jmp(x_dec,'next')  # we need buffer size -1 except on first ??

	wrap_target()  # loop when buffer size has been reached
	mov(y,x)       # copy buffer size to y

	label('next')  # loop when buffer size not yet reached
	pull(block)    # retrieve adc value in 32 bits format

	mov(isr,osr)
	in_(null,24)
	push(block)
	mov(isr,osr)
	in_(null,16)
	push(block)
	jmp(y_dec,'next')  # no irq until 
	irq(0)
	# wrap() # Not needed, program auto wraps on end

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
		# create pre-allocated bound function reference to work in "schedule"
		self.NewBuffer_ref = self.NewBuffer # Called back on ping and pong

		self.fs = fs
		self.t_us = 1000000 // fs
		self.ch_mask = 0
		self.n = 1
		self.bits = bits
		self.buf = array.array('H', [0])
		self.buf_size = buf_size
		self.sm = None
		
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

	# to help player, the first 3 words in a file can be set to:
	# w1: 0xFABC (Magic value indicating header is present)
	# w2: sampling rate/10 (ADC sampling rate so per channel is w2*10/ch_count)
	# w3 channel mask bit 0,1,2,3,4 (4 for temperature sensor)
	def WriteFileHdr(self, file):
		hdr =  array.array('H', [0xFABC, self.fs//10, self.ch_mask] )
		file.write(hdr)
	
	# If file object is present, will write to file. CB(buf) will be called if provided
	#@micropython.native
	def Start(self, file=None, CB=None, pio_sm=0): 
		if (file is None) and (CB is None): raise(Exception('"file" or "CB" required'))

		self.CB = CB
		self.file = file

		bs = self.buf_size
		bs_bits = math.log2(bs*4) # 2 buffers, 2 bytes per sample		
		if str(bs_bits)[-2:]!='.0': raise(Exception('"Buffer Size" must be a power of 2'))
		if pio_sm > 3: raise(Exception('"pio_sm" must be <= 3'))

		PIOTX = 0x50200010 + 4 * pio_sm

		# setup state machine (if not already done)
		if self.sm is None:
			self.sm = rp2.StateMachine(pio_sm, adc_bridge) 
			self.irq = self.sm.irq(self.buf_irq)
		else:
			self.sm.restart()

		self.sm.active(1)

		self.sm.put(bs) # set buffer size to get timely IRQs 

		# prepare ping pong. 
		# Need 2x, but allocate 3x to insure dma wrap alignment is possible
		self.buf =  array.array('H', [0xaa55] * (bs * 4))

		# find a proper wraping address inside oversized buffer
		s0 = uctypes.addressof(self.buf)
		bs_bits = int(bs_bits)
		mask = 2**bs_bits-1
		ofst = (mask + 1) - (s0 & mask)

		s0 += ofst # proper start address. osft is in bytes

		# (buff start, buffer last) for each ping pong buffer
		ofix = ofst // 2
		self.pp = [ofix, ofix + bs]  
		self.ppix = 0

		#print(self.pp)
		#time.sleep(2)

		# DMA channel used to copy adc to dword pio FIFO
		self.dma_adc = Dma(data_size=4) # acquisition
		self.dma_adc.SetDREQ(36)   # DREQ_ADC = 26
		self.dma_adc.SetAddrInc(0, 0) # No increment: adc to PIO FIFO = fixed addresses
		self.dma_adc.SetReadadd(Adc.FIFO)		
		self.dma_adc.SetWriteadd(PIOTX) 	
		self.dma_adc.SetCnt(0x3fffffff) # @22Ksps, this is > 54 hours
		self.dma_adc.Enable()

		# DMA Channel used to copy pio FIFO bytes (2 per sample) to ram
		self.dma_ram = Dma(data_size=1) # chain 1 blk to repeat
		self.dma_ram.SetDREQ(4+pio_sm)  # DREQ_PIO0_RX1 to RX3
		self.dma_ram.SetAddrInc(0, 1)   # always read from PIO, wrapped write
		self.dma_ram.SetReadadd(PIOTX + 0x13) # matching RX is + 0x13 (byte access)
		self.dma_ram.SetWriteadd(s0)      # WRITE_ADDR, TRANS_COUNT_TRIF
		self.dma_ram.SetWrap(bs_bits, 1)  # set wrap bits, and wrap on write 
		self.dma_ram.SetCnt(0x3fffffff) # 27hrs at 22ksps
		self.dma_ram.Enable()

		# setup Adc
		# set ADC clock
		if self.fs<733: raise(Exception('Sampling rate must be at least 733Hz'))
		if self.fs>500000: raise(Exception('Sampling rate must be <= 500kHz'))
		div = (48000000 << 8) // self.fs # lower 8 bits are fractional
		mem32[Adc.DIV] = div

		self.cs &= ~(0x1F << 16)			# clear RROBIN
		self.cs |= self.ch_mask << 16		# set RROBIN and START_MANY
		mem32[Adc.FCS] = 0b1001 | (1<<24) 	# FIFO en + DREQ_EN + THRESH = 1
		mem32[Adc.CS] = self.cs         	# setup adc except START

		# debug, show info before start (comment)
		# self.Info('\33c')
		# print('\nStarting in 2 sec...\n')
		# time.sleep(2)

		#start dma
		self.dma_adc.Trigger()
		self.dma_ram.Trigger()
		self.cs |= 8  # set START_MANY
		mem32[Adc.CS] = self.cs  # start adc		

	def Stop(self):
		self.cs &= ~8 # stop acquisition. RROBIN: MANY =  0
		mem32[Adc.CS] = self.cs
		Dma.Abort([self.dma_adc.ch, self.dma_ram.ch])
		self.dma_adc.DeInit()
		self.dma_adc.DeInit()
		self.sm.active(0)
	
	# interrupt routine triggered by pio code every "Adc.buf_size" sample
	# Only schedule handling function
	@micropython.viper
	def buf_irq(self,pio):
		micropython.schedule(self.NewBuffer_ref, None)

	# function called every time a buffer is ready to process
	@micropython.viper
	def NewBuffer(self, _):
		ix = self.pp[self.ppix]
		mv = memoryview(self.buf[ix:ix+self.buf_size])
		if self.file:
			self.file.write(mv)
		else:
			CB(mv)
		i = int(self.ppix)
		i = 1 - i
		self.ppix = i
		
	# For debug. Suggests using buf_size <= 16 when debugging 
	def ShowPingPong(self):
		print('ping:',memoryview(self.buf[self.pp[0]:self.pp[0] + self.buf_size]).hex())
		print('pong:',memoryview(self.buf[self.pp[1]:self.pp[1] + self.buf_size]).hex())
		print()

	def Info(self,title=''):
		if (title): print(title)
		cs = mem32[Adc.CS]
		print('ADC:')
		print('EN:', cs & 1, '  TS:', field(cs,1,1), '  ONCE:', field(cs,2,1), \
			'  MANY:', field(cs,3,1), '  READY:', field(cs,8,1))
		print('AINSEL:', field(cs,12,3), '  RROBIN:', bin(field(cs,16,5))[2:], \
			'  DIV:', mem32[Adc.DIV] / 256)
		self.dma_adc.Info('\nADC to PIO')
		self.dma_ram.Info('PIO to RAM')
		self.ShowPingPong()

	# For debug. Check pio FIFOs (before starting DMA channels)
	# should output 1 2 3 4 5 6 7 8 9 a b c d e f 0 1 2 3 ...
	def TstPIO(self, cnt=20):
		for n in range(0,cnt):
			a = ((n*2) + 1) % 16
			b = (a + 1) % 16
			self.sm.put(a + (b << 8))
			while self.sm.rx_fifo()>0:
				print(hex(self.sm.get()), end = ' ')

# Test it.
'''
# test non Dma acquisition
adc = Adc(chs=4,fs = 2) # test with ch4: temp sensor
print('n=',adc.n, ' mask=', bin(adc.ch_mask), ' chs=', adc.chs)
while True:
	print(adc.Read(5), end=' T=')
	print(27-(3.3*adc.buf[0]/4096 - 0.706)/.001721)
	time.sleep_ms(200)
'''

'''
# to switch off SD Card test, comment import and SDCard.xx() lines
# test dma interface 
def tst():
	print('\33c') # clear screen
	machine.freq(260000000)
	from sdcard import SDCard

	SDCard.Mount()
	adc = Adc(chs=0, fs = 22000, buf_size=2048)

	f = open("/sd/test.bin", "w")  # change to '/sd/test.bin' for sd card
	adc.WriteFileHdr(f)
	adc.Start(file=f)
	print('Starting acquisition 5 sec...')
	time.sleep(5)
	adc.Stop()
	f.close()
	SDCard.UMount()
	print('Done')
tst()
'''

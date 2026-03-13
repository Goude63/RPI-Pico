# ----------------------------------------------------
# pio code for DAC9922 parallel com
# in test code: D0-D15 = GP0-GP15 on final GP10-GP 
# -------------------------------------
machine.freq(200_000_000) 

# must run at 100MHz clock. 1 ns per clock
from rp2 import PIO, asm_pio, StateMachine
from machine import Pin, PWM
from dma import Dma
import time, array, uctypes
from CLT1100 import CLT1100
import math

@asm_pio(
	out_init=(PIO.OUT_LOW,) * 21, 
	set_init=PIO.OUT_LOW,
	autopull=False,
	out_shiftdir=PIO.SHIFT_RIGHT,
	fifo_join=PIO.JOIN_TX)
def _DAC8822():
	pull(block)         # pull takes a value from tx fifo into osr    
	out(pins,21) [2]    # D0-D15 + nc + A0 + U1/U2 and set /WR low + Tas 10ns

	# debug delay 0.25 sec
	# mov(x,isr)
	# label('d1')
	#jmp(x_dec,'d1')[9]  # 10 ms

	set(pins,1)         # set /WR to 1 (stop the write operation)
	# nop() [9]

	# debug delay 0.25 sec
	# mov(x,isr)
	# label('d2')
	# jmp(x_dec,'d2')[3]  # 2ms

SMID = 0
PIOTX = 0x50200010 + 4 * SMID
sm = StateMachine(SMID, _DAC8822, 200_000_000, out_base=Pin(10),set_base=Pin(30))
enc = CLT1100(10, 32, 40 )

# test to send multi channel data
def tst2(CH_CNT):
	global dmas,bufs

	pwm = PWM(22,freq=2500,duty_u16=8192)
	tst_size = 4096
	dmas = []; cdmas = []; bufs = []; caddr = array.array('L',[0]*4) 
	for i in range(CH_CNT):
		dma = Dma(data_size=4)
		dma.SetAddrInc(1,0)   # walk buffer but fixted PIO TXFIFO register address
		dmas.append(dma)
		blk = array.array('L',[0x7FFF]*tst_size) # init to mid point
		caddr[i] = uctypes.addressof(blk)
		dma.SetChData(blk,blk,tst_size,False)
		dma.SetWriteAdd(PIOTX)
		dma.SetTREQ(0, 1, 900)
		# dma.SetDREQ(35)  # in debug: send at PWM22/3A wrap speed = slow

		ch = (i + 4) << 17
		#ch = (i + 2) << 17
		for j in range(tst_size):		
			#blk[j] = int(32768.01 + 32767.01 * math.sin((float(j/tst_size))*2*math.pi)) + ch
			if i == 0:	blk[j] = int(32768.01 + 32767.01 * math.sin((float(j/tst_size))*2*math.pi)) + ch
			#if i == 1: blk[j] = int(65535 * j / tst_size) + ch
			blk[j] = 0x8000 + ch
		# print(blk)
		bufs.append(blk)

	# setup chain Dma channels that loops data
	for i in range(CH_CNT):
		cdma = Dma(data_size=4)
		cdma.SetAddrInc(0,0) # re-write same data same place (data buffer start address at READ_ADDR)
		dmas[i].ChainTo(cdma.ch)		
		cdma.SetReadAdd(uctypes.addressof(caddr) + 4 * i) 
		# print(hex(uctypes.addressof(caddr) + 4 * i))
		cdma.SetWriteAdd(Dma.BASE_DMA + dmas[i].ch*0x40 + 0x3c)  # AL3_READ_ADDR_TRIG, will re-trigger dma
		cdma.SetCnt(1)
		cdmas.append(cdma)

	# Dma.Scan()
	for i in range(CH_CNT):
		dmas[i].Trigger()
	
	# time.sleep(1)
	# Dma.Scan()

	while True:
	#for i in range(10):
		# print('\33c',end='') # clear screen in most terminals
		#for i in range(CH_CNT):
		#	dmas[i].Info()
		#	cdmas[i].Info()
		# Dma.Scan()
		time.sleep(1)

@micropython.native
def write_ch(ch, v):
	ch = (ch % 2) + 2 # I am now debuging with a u1 missing (only ch 2 and 3)
	v = min(65535, max(0, v))
	# ch + 2 = 2, 3, 4 or 5 =  10, 11, 100, 101 == what we need for u1/u2
	sm.put(v + ((ch + 2) << 17))  # this also makes /w = 0

def tst1():
	enc.GetTurn() # flush possible pending turn

	v = [1638] * 4
	for ch in range(4): write_ch(ch, v[0])
	ch = 0
	while True:
		if enc.Btn(): 
			ch = (ch + 1) % 4 
			print(f'ch={ch}')
			while enc.Btn(): pass
			enc.GetTurn() # flush rotation
		else:
			r = enc.GetTurn()
			if r:
				v[ch] = min(65535, max(0, v[ch] + r * 1638))
				write_ch(ch, v[ch])
				print(f'ch={ch}, v={v[ch]}')
		time.sleep(0.5)

@micropython.native
def tst0():
	v = [0, 32768, 65535]
	ix = 0
	n = 0
	while n<10000:
		write_ch(0, v[ix])
		ix += 1
		if ix >= 3: ix = 0
		write_ch(1, v[ix])
		n += 1
		time.sleep_us(60)

def main():
	print('\33c',end='') # clear screen in most terminals
	rst = Pin(31,Pin.OUT,value=0)
	time.sleep_us(1)
	rst.value(1)
	
	# for debug: set y for loop count to slowdown for human eye led blink
	# The 3 following lines can optionally be commented for final 
	#sm.put(100_000) # 1ms per clock @ 100MHz  
	#sm.exec('pull()')
	#sm.exec('mov(isr, osr)')	# store end write code in PIO register y 

	sm.active(True)

	tst2(2)

	write_ch(0, 65535)
	write_ch(1, 65535)
	time.sleep(1)

	rst.value(0)
	time.sleep_us(1)
	rst.value(1)

	time.sleep(5)

main()
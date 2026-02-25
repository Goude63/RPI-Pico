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

@asm_pio(
	out_init=(PIO.OUT_LOW,) * 21, # 21
	autopull=False,
	out_shiftdir=PIO.SHIFT_RIGHT,
	fifo_join=PIO.JOIN_TX)
def _DAC8822():
	pull(block)         # pull takes a value from tx fifo into osr    
	out(pins,21) [9]    # D0-D15 + nc + A0 + U1/U2 and set /WR low + Tas 10ns

	# debug delay 0.25 sec
	mov(x,isr)
	label('d1')
	jmp(x_dec,'d1')[9]  # 10 ms

	mov(pins,y)         # y set to end transfer: rise /wr and lower LDAC (U1-U2)

	# debug delay 0.25 sec
	mov(x,isr)
	label('d2')
	jmp(x_dec,'d2')[1]  # 2ms

SMID = 0
PIOTX = 0x50200010 + 4 * SMID
sm = StateMachine(SMID, _DAC8822, 100_000_000, out_base=Pin(0))

def tst1():
	START = 3
	a = 2            # u1 ch 0
	d = START
	while True:
		v = d + (a<<17)
		sm.put(v)
		time.sleep(0.5)
		sm.put(0)
		# print(hex(v), a)
		time.sleep(0.2)
		a = a+1 if a<5 else 2
		d = d << 1 if d<0xFFFF else START

# test to send multi channel data
def tst2():
	global dmas,bufs

	pwm = PWM(22,freq=25,duty_u16=8192)
	CH_CNT = 4 # 4 later
	tst_size = 32
	dmas = []; cdmas = []; bufs = []; caddr = array.array('L',[0]*4) 
	for i in range(CH_CNT):
		dma = Dma(data_size=4)
		dma.SetAddrInc(1,0)   # walk buffer but no inc for fixted PIO FIFO data address
		dmas.append(dma)
		blk = array.array('L',[0x7FFF]*tst_size) # init to mid point
		caddr[i] = uctypes.addressof(blk)
		dma.SetChData(blk,blk,tst_size,False)
		dma.SetWriteAdd(PIOTX)
		# dma.SetTREQ(0, 1, 32768) # DMA Timer 0 @ 3kHz		
		dma.SetDREQ(35)  # in debug: send at PWM22/3A wrap speed = slow
		for j in range(tst_size):
			ch = (j + 2) << 17
			if   i==0: blk[j] = 2 ** (j%16) 
			elif i==1: blk[j] = 2 ** (j if j<16 else 31-j)
			elif i==2: blk[j] = (3 << (j%15)) 
			else: blk[j] = (3 << (16-(j%15))) & 0xFFFF
			blk[j] += ch
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

def main():
	print('\33c',end='') # clear screen in most terminals
	rst = Pin(21,Pin.OUT,value=0)
	time.sleep_us(1)
	rst.value(1)

	# for debug: set y to loop count for slow down delay
	sm.put(100_000) # 1ms per clock @ 100MHz  
	sm.exec('pull()')
	sm.exec('mov(isr, osr)')	# store end write code in PIO register y 

	# set /wr high and U1/U2 low. Data mid point
	sm.put((0b1000<<17) + 0x7FFF)  
	sm.exec('pull()')
	sm.exec('mov(y, osr)')	# store end write code in PIO register y 
	sm.active(True)

	tst2()

main()
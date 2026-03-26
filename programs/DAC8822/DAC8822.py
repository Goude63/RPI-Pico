# ----------------------------------------------------
# pio code for DAC9922 parallel com
# in test code: D0-D15 = GP0-GP15 on final GP10-GP 
# -------------------------------------

# must run at 100MHz clock. 1 ns per clock
from rp2 import PIO, asm_pio, StateMachine
from machine import Pin, PWM
import time, array, uctypes, math, gc, random
from CLT1100 import CLT1100
from dma import Dma

gc.collect()

# this single state machine handles
@asm_pio(
	out_init=(PIO.OUT_LOW,) * 21,  # 16 bits data + spacer + U1,U2, /WR
	set_init=PIO.OUT_LOW,
	autopull=False,
	out_shiftdir=PIO.SHIFT_RIGHT,
	fifo_join=PIO.JOIN_TX)
def _DAC8822():
	pull(block)         # pull takes a value from tx fifo into osr    
	out(pins,21) [2]    # D0-D15 + nc + A0 + U1/U2 and set /WR low + Tas (min 10ns)
	set(pins,1)         # set /WR to 1 (stop the write operation)	


SMID = 0
PIOTX = 0x50200010 + 4 * SMID

class DAC8822:
	GBL_DAC = None

	# test to send multi channel data
	#def tstDMA(CH_CNT=2, buf_size=8, fdiv = 1024 ):
	#	global dmas,bufs
	def __init__(self,chnl_cnt=4, buf_size=4096, smid = SMID, smr=None):

		if smr is None: smr = machine.freq()

		self.sm = StateMachine(smid, _DAC8822, smr, out_base=Pin(10),set_base=Pin(30))
		self.sm.active(1)

		self.ChConfig =[(0,0,0,0,0,0)]*chnl_cnt
		self.MaxVRef = [1.0, 1.0] # one vref per 2 channel
		self.running = [False] * chnl_cnt
		self.ch_cnt = [0] * chnl_cnt

		self.dmas = []  # data dma channels 
		self.cdmas = [] # re-trigger dma control channels
		self.bufs = []  # data buffers
		self.ctrl_blk = array.array('L',[0]*(chnl_cnt*2)) # size and rd address for each data buffer
		self.PingPongIx = [1] * chnl_cnt # so that first usage will use lower half
		for i in range(chnl_cnt):
			self.buf_size = buf_size
			dma = Dma(data_size=4)
			dma.SetAddrInc(1,0)   # walk buffer but fixted PIO TXFIFO register address
			self.dmas.append(dma)
			# each channel has 2 buffers to allow prepare/activate with minimum signal cut
			blk = array.array('L',[0x7FFF]*(buf_size*2)) # init to mid point
			self.bufs.append(blk)

			# this part is not really used at init and repeated when creating channel data
			self.ctrl_blk[2*i] = buf_size
			self.ctrl_blk[2*i+1] = uctypes.addressof(blk)
			dma.SetChData(blk,blk,buf_size,False)
			dma.SetWriteAdd(PIOTX)
			dma.SetTREQ(0, 1, 8132)  # temporary slow rate that will not be used

		# setup chain Dma channels that loops data
		for i in range(chnl_cnt):
			self.cdma = Dma(data_size=4)
			self.cdma.SetAddrInc(0,0) # re-write same data same place (data buffer start address at READ_ADDR)
			self.dmas[i].ChainTo(self.cdma.ch)		
			self.cdma.SetReadAdd(uctypes.addressof(self.ctrl_blk) + 8 * i) # 2 long for each blk=> cnt and buf addr
			# print(hex(uctypes.addressof(self.ctrl_blk) + 8 * i))
			self.cdma.SetWriteAdd(Dma.BASE_DMA + self.dmas[i].ch*0x40 + 0x3c)  # AL3_READ_ADDR_TRIG, will re-trigger dma
			self.cdma.SetCnt(1)
			self.cdmas.append(self.cdma)
	
		# for i in range(CH_CNT):	dmas[i].Trigger() # start all
		# while True:	time.sleep_ms(50)
		
	# shape can be 0-5 (square, sin, triangle left saw, right saw or random)
	# shape can also be a file name containing the binary data 
	# fr: frequency (Hz), am: amplitude (V), of: voltage offset (V), ph: phase (degr)
	def CreateData(self, ch, shape, fr, am, of, ph, dt, start=False):

		# calculate and setup vref by 2 ch group
		maxv = am + abs(of)
		self.ChConfig[ch] = (shape, fr, am, of, ph, dt, maxv)

		ass_ch = [1,0,3,2][ch] # other channel on same chip/vref
		if len(self.ChConfig(ass_ch))<7: ass_ch = -1

		if ass_ch >= 0:
			max_vref = max(maxv, self.ChConfig[ass_ch][6]) # max v of same chip vref
		else: max_vref = maxv
		
		if max_vref != self.MaxVRef[ch // 2]:
			self.MakeData(ass_ch, max_vref)     # re-calculate 16 bits values from new vref
			self.MaxVRef[ch // 2] = max_vref

		self.MakeData(ch, max_vref, start)
		
	# create waveform. temporarily, min fr = 1 Hz TBF use PWM as DMA timer for low frequencies
	@micropython.native
	def MakeData(self, ch, vref, specs = None, start=None):  
		if ch < 0 : return
		if start is None: start = self.running[ch]

		(shape, fr, am, of, ph, dt) = self.ChConfig[ch]  if specs is None else specs

		# TBD add arpitrary file support (pretty easy)
		# ELSE ... calculate appropriate buffer size according to freq
		# try having even sample count and as precise as possible rate

		if shape == 5:
			cnt = self.buf_size
			clkdiv = 256
		else:
			max_fs = machine.freq() / 16.0
			cnt = max_fs / float(fr)  # calculate float to check precision

			if cnt > self.buf_size:	
				cnt = int(cnt / round((cnt/self.buf_size) + 1))
			else: cnt = round(cnt)
			if cnt & 1: cnt-=1
			clkdiv = int(round(machine.freq() / (cnt*fr)))

		print(f'fr={fr}, cnt={cnt}, clkdiv={clkdiv}, actual fr={machine.freq()/clkdiv/cnt}')

		# write data in pong (of ping pong) buffer
		buf = self.bufs[ch]
		ppo = 0 if self.PingPongIx[ch] else self.buf_size // 2

		addr = (ch + 2) << 17
		half = cnt // 2
		x = 0; dx = 2 * math.pi / cnt; 
		cph = math.pi*ph/180  if shape == 1 else ph * cnt / 360
		for j in range(cnt):
			i = (j + cnt - cph) % cnt
			if   shape == 0: v = am if i>=half else 0
			elif shape == 1: v = am * math.sin(x-cph); x += dx
			elif shape == 2: v = am - 2*am*abs((i-half)/half)	# triangular
			elif shape == 3: v = -am + 2*am*abs((cnt-i)/cnt)	# left sawtooth
			elif shape == 4: v = am - 2*am*abs((cnt-i)/cnt)		# right sawtooth
			elif shape == 5: v = am - 2*am*random.random()		# noise

			v += of
			buf[j+ppo] = addr + int(max(0, min(65535, round(32768 + 32768*v/vref))))

		self.ch_cnt[ch] = cnt
		self.PingPongIx[ch] = 1 - self.PingPongIx[ch]

	# for debugging
	def GetChData(self, ch):
		l = self.ch_cnt[ch]
		r = array.array('I', [0]*l)
		ppo = self.buf_size // 2 if self.PingPongIx[ch] else 0
		for i in range(l): 
			r [i] = self.bufs[ch][i+ppo] & 0xFFFF
		return r

if __name__ == "__main__":
	
	print('\33c')
	gc.collect()
	dac = DAC8822(4, 8*1024)
	gc.collect()

	for f in [100000]: # [0.5, 1, 1000, 20000, 1e6, 5e6]:
		# (shape, fr, am, of, ph, dt,)
		dac.MakeData(0, 5, (5, f, 5, 0, 0, 50))

	# print(dac.GetChData(0))

		
	


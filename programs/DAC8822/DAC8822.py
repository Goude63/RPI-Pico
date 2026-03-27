# ----------------------------------------------------
# pio code for DAC9922 parallel com
# in test code: D0-D15 = GP0-GP15 on final GP10-GP 
# -------------------------------------

# must run at 100MHz clock. 1 ns per clock
from rp2 import PIO, asm_pio, StateMachine
from machine import Pin, PWM, mem32
import time, array, uctypes
import math, gc, random
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
	out(pins,21) [1]    # D0-D15 + nc + A0 + U1/U2 and set /WR low + Tas (min 10ns)
	set(pins,1)         # set /WR to 1 (stop the write operation)	

SMID = 0
PIOTX = 0x50200010 + 4 * SMID

class DAC8822:
	GBL_DAC = None

	# test to send multi channel data
	#def tstDMA(CH_CNT=2, buf_size=8, fdiv = 1024 ):
	#	global dmas,bufs
	def __init__(self,chnl_cnt=4, buf_size=4096, smid = SMID, sm_clk=None):

		if sm_clk is None: sm_clk = machine.freq()

		self.sm = StateMachine(smid, _DAC8822, sm_clk, out_base=Pin(10),set_base=Pin(30))
		
		self.rst = Pin(31,Pin.OUT,value=0)
		self.ResetDAC()
		self.sm.active(True)

		self.ChConfig =[()]*chnl_cnt
		self.HW_Vref = [5.0, 5.0] # one vref per 2 channel
		self.running = [False] * chnl_cnt
		self.ch_cnt = [0] * chnl_cnt

		self.dmas = []  # data dma channels 
		self.cdmas = [] # re-trigger dma control channels
		self.bufs = []  # data buffers
		self.ctrl_blk = array.array('L',[0]*(chnl_cnt)) # address for each data buffer
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
			dma.SetWriteAdd(PIOTX)
			self.SetupDMA(i, buf_size, 8192)

		# setup chain Dma channels that loops data
		for i in range(chnl_cnt):
			cdma = Dma(data_size=4)
			cdma.SetAddrInc(0,0) # re-write same data same place (data buffer start address at READ_ADDR)
			self.dmas[i].ChainTo(cdma.ch)		
			cdma.SetReadAdd(uctypes.addressof(self.ctrl_blk) + 4 * i) # data buf addr to reload
			cdma.SetWriteAdd(Dma.BASE_DMA + self.dmas[i].ch*0x40 + 0x3c)  # Alias3 CNT + READ_ADDR_TRIG
			cdma.SetCnt(1) # only start address. Size from data dma cnt reg (relods)
			self.cdmas.append(cdma)

	def ResetDAC(self):
		self.rst.value(0)
		time.sleep_ms(1)
		self.rst.value(1)

	# setup dma for new data source (ping pong based)
	@micropython.native
	def SetupDMA(self, ch, size, clkdiv):
		dma = self.dmas[ch]
		addr = uctypes.addressof(self.bufs[ch])
		if self.PingPongIx[ch]: addr+= 2 * self.buf_size # = 4 * (BS//2) 

		# setup auto reload control block
		self.ctrl_blk[ch] = addr

		# setup data DMA. 
		dma.SetTREQ(0, 1, clkdiv)  

		# If channel is already running, ctrl block will do this at current block end
		dma.SetCnt(size) # will be reloaded on next trigger ( chain fom cdma or in Start() )
		if not self.running[ch]: dma.SetReadAdd(addr)
			
		
	# shape can be 0-5 (square, sin, triangle left saw, right saw or random)
	# shape can also be a file name containing the binary data 
	# fr: frequency (Hz), am: amplitude (V), of: voltage offset (V), ph: phase (degr)
	@micropython.native
	def CreateData(self, ch, shape, fr, am, of=0, ph=0, dt=50, start=False):
		# calculate and setup vref by 2 ch group
		if am > 10: am = 10
		if of>10: of =10
		maxv = am + abs(of)
		self.ChConfig[ch] = (shape, fr, am, of, ph, dt, maxv)

		ass_ch = [1,0,3,2][ch] # other channel on same chip/vref
		if len(self.ChConfig[ass_ch])==0: ass_ch = -1

		if ass_ch >= 0:
			max_vref = max(maxv, self.ChConfig[ass_ch][6]) # max v on same hw_vref
		else: max_vref = maxv
		
		# re-scale associated channel if needed
		hwvref = self.HW_Vref[ch // 2]
		if max_vref>hwvref or (max_vref/hwvref < 0.9):
			self.MakeSignal(ass_ch, max_vref)     # re-calculate 16 bits values from new vref
			self.HW_Vref[ch // 2] = max_vref
		self.MakeSignal(ch, max_vref, start=start)


	# create waveform. temporarily, min fr = 1 Hz TBF use PWM as DMA timer for low frequencies
	@micropython.native
	def MakeSignal(self, ch, vref, specs = None, start=None):  
		if ch < 0 : return
		if start is None: start = self.running[ch]
		if specs is None: specs = self.ChConfig[ch]
		(shape, fr, am, of, ph, dt, maxv) = specs 

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

		# print(f'fr={fr}, cnt={cnt}, clkdiv={clkdiv}, actual fr={machine.freq()/clkdiv/cnt}')

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
		self.SetupDMA(ch, cnt, clkdiv)
		if start: self.Start(ch)
	
	# chs can be a channel number or a list to stop
	def Start(self, chs):
		if type(chs) != type([]): chs = [chs]
		for ch in chs:
			if not self.running[ch]:
				self.dmas[ch].Trigger()
				self.running[ch] = True

	# chs can be a channel number or a list to stop
	def Stop(self, chs):
		if type(chs) != type([]): chs = [chs]
		dma_ch_stoplst = []
		for c in chs: 
			if self.running[c]:
				dma_ch_stoplst.append(self.dmas[c].ch)
				dma_ch_stoplst.append(self.cdmas[c].ch)
				self.running[c] = False
		if len(dma_ch_stoplst):	Dma.Abort(dma_ch_stoplst)

	# for debugging
	def GetChData(self, ch):
		l = self.ch_cnt[ch]
		r = array.array('I', [0]*l)
		ppo = self.buf_size // 2 if self.PingPongIx[ch] else 0
		for i in range(l): 
			r [i] = self.bufs[ch][i+ppo] & 0xFFFF
		return r

if __name__ == "__main__":

	@micropython.native
	def write_ch(sm, ch, v):
		ch = (ch % 2) + 2 # I am now debuging with a u1 missing (only ch 2 and 3)
		v = min(65535, max(0, v))
		# ch + 2 = 2, 3, 4 or 5 =  10, 11, 100, 101 == what we need for u1/u2
		sm.put(v + ((ch + 2) << 17))  # this also makes /w = 0
	
	gc.collect()
	dac = DAC8822(4, 2*1024)
	gc.collect()

	# write_ch(dac.sm, 1, 65535);	time.sleep(2)

	while True:
		for shape in range(6):
			# dac.Stop([2,3])
			dac.CreateData(2, shape, 1000, 5, start=True)
			dac.CreateData(3, (shape + 1)%6, 1000, 5, start=True)
			# dac.Start([2,3])
			print('\33c')
			Dma.Scan()
			gc.collect()
			print(f'Mem={gc.mem_free()}')
			for n in range(30): time.sleep_ms(100)

from dma import Dma
import array, math, uctypes
from machine import PWM, Pin

# PWM signal generator
class SigGen:
	FREE_DMA = list(range(12)) # by default, all DMA ch available
	USED_PWM_CH = []
	
	# if some DMA channels are used by something else, exclude them here
	@staticmethod
	def ExcludeDMA(list): 
		for x in list: SigGen.FREE_DMA.remove(x)

	# signal values must be in range (0, 65535)
	# pf is the signal generator frequency (PWM's pulse frequency)
	# excludeDMA prevent this call from using some DMA channels (used elsewhere)
	# Currently, gpio must be even. May be improved later
	def __init__(self, gpio = 12, pf = 10000):
		self.pf = pf
		self.gpio = gpio
		self.running = False
		self.pwm_ch = (gpio & 0xF) >> 1 
		if self.pwm_ch in SigGen.USED_PWM_CH: 
			raise(Exception('PWM channe ', self.pwm_ch,' already in use'))
		SigGen.USED_PWM_CH.append(self.pwm_ch)
		self.pwm = PWM(Pin(gpio), freq=pf, duty_u16=32768) # init on center
		self.zero = mem32[0x4005000c + 0x14 * self.pwm_ch] # actual CC value for zero

	# Note that if a decoupling cap is used, SetDC() becomes pretty useless
	def SetDC(self, v = 1.0):
		self.Stop()
		if v>3.3: v = 3.3
		dt = int((v / 3.3) * 65535)
		self.pwm.duty_u16(dt)

	# vals are values between 0 and 65536
	def Start(self):
		self.Stop()
		if len(SigGen.FREE_DMA) < 2: raise(Exception('No DMA channel available'))

		# DMA channel used to send wave data
		self.dma_w = Dma(SigGen.FREE_DMA.pop(0), data_size=4) # waveform
		self.dma_w.SetDREQ(24 + self.pwm_ch)   # DREQ_PWM_WRAP0 = 24
		self.dma_w.SetAddrInc(1, 0) # Read increment, no write inc (pwm register)
		self.dma_w.SetReadadd(uctypes.addressof(self.wav))		
		self.dma_w.SetWriteadd(0x4005000c + 0x14 * self.pwm_ch) # CHx_CC register		
		self.dma_w.SetCnt(len(self.wav))

		# DMA Channel used to re-trigger dma_w
		self.dma_c = Dma(SigGen.FREE_DMA.pop(0), data_size=4) # chain 1 blk to repeat
		self.dma_w.ChainTo(self.dma_c.ch) # to retrigger
		self.dma_c.SetDREQ(0x3f) # no DREQ
		self.dma_c.SetAddrInc(0, 0) # re-set same ctrl reg on same value every time
		self.dma_chain = array.array("L",[0,0]) # only need one, extra safety
		self.dma_chain[0] = uctypes.addressof(self.wav) # reset address on each repeat
		self.dma_c.SetReadadd(uctypes.addressof(self.dma_chain))
		self.dma_c.SetWriteadd(self.dma_w.TrigCtrlReg + 0x30) # READ_ADDR_TRIG 
		self.dma_c.SetCnt(1)
		self.dma_c.Enable()
		self.dma_w.Trigger()

		self.running = True

	def Stop(self):
		if not self.running: return
		self.dma_c.Enable(0)
		self.dma_w.Enable(0)
		lst = [self.dma_w.ch, self.dma_c.ch]
		Dma.Abort(lst)
		SigGen.FREE_DMA += lst
		self.running = False

	# a: amplitude as in a * sin(wt). in Volts. Actual amplitude depends on RC filter
	# shape = "sin", "saw" or "tri".  f is waveform frequency in hz
	# the function generates one cycle data to be repeated by SigGen.
	def SetWav(self, a=1.65, shape = "sin", f=2000, go = True, ch='A'):
		cnt = self.pf // f
		r = array.array("L",[0]*cnt)
		a = abs(a)
		if a>1.65: a=1.65
		ai = int((a / 1.65) * self.zero) # zero is also half the max on value for pwm
		d = (2*math.pi)/cnt
		if shape == "tri": cnt = cnt // 2
		for i in range(cnt):
			if   shape == "sin": y = ai + int(ai * math.sin(i * d)) # y in [0..res-1]
			else: y = int(2 * ai * ( i / cnt)) # saw and tri            
			r[i]=y
		if shape == "tri":
			for i in range(cnt): r[i+cnt]=r[cnt-i-1]
		self.wav = r # TBD: or ch A and B<<16 to allow supported 2ch per PWM slice
		if go: self.Start()

	def DeInit(self):
		self.__del__()

	def __del__(self):
		self.Stop()
		self.pwm.deinit()

# test stuff. Comment when using this file as import
#'''
print('\33c') # clear screen

mhz, khz = (1000000, 1000)
machine.freq(256 * mhz)
sg = SigGen(14, pf=8*mhz)
sg.SetWav(f = 2*mhz, go=True)
print('steps: ',sg.zero)
#'''



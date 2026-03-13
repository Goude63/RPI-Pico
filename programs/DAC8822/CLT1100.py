# ----------------------------------------------------
# pio code for CLT1100 rotary encoder
# -------------------------------------

# must run at 100MHz clock. 1 ns per clock
from rp2 import PIO, asm_pio, StateMachine
from machine import Pin, Timer
import rp2

@asm_pio(out_init=(PIO.IN_HIGH, PIO.IN_HIGH), 
		 fifo_join=PIO.JOIN_RX,
		 out_shiftdir=PIO.SHIFT_RIGHT)
def _CLT1100():
	label('wait_11')
	mov(osr,pins)
	out(x,1)
	jmp(not_x,'wait_11') # A not 1 wait
	out(x,1)
	jmp(not_x,'wait_11') # B not 1 wait

	label('11')
	mov(osr, pins)
	out(x,1)  # check A
	jmp(not_x,'RR') # A changed first => RR
	out(x,1)
	jmp(x_dec,'11')
	set(x,0)
	jmp('pushx') # B changed first => RL

	label('RR')
	set(x,1)  # 1 for RR

	label("pushx") 
	mov(isr,x)
	push(noblock)

class CLT1100:
	POOL_LST = []
	TIMER = None

	@staticmethod
	@micropython.native
	def PoolEncoders(timer):
		for e in CLT1100.POOL_LST: e.Pool()

	@staticmethod
	def Register(encoder):
		CLT1100.POOL_LST.append(encoder)
		if len(CLT1100.POOL_LST) == 1:
			# setup timer irq
			CLT1100.TIMER = Timer(period=200, mode=Timer.PERIODIC, 
				callback=CLT1100.PoolEncoders)
	
	@staticmethod
	def TerminatePool():
		CLT1100.TIMER.deinit()

	def __init__(self, smix, p1, push = None): # p1, p1+1: encoder A,C, p1+2: push 
		if push is None: push = p1 + 2
		Pin(p1,Pin.IN, Pin.PULL_UP)
		Pin(p1+1,Pin.IN, Pin.PULL_UP)
		self.btn = Pin(push, Pin.IN, Pin.PULL_UP)

		gpio = rp2.PIO(smix//4)
		if p1>=32 and not 'GPIO16' in str(PIO.gpio_base(gpio)): 
			PIO.gpio_base(gpio, 16)
		
		self.sm = StateMachine(smix, _CLT1100, 5000, in_base=Pin(p1))
		self.sm.active(1)		
		self.regix = CLT1100.Register(self)
		self.pos = 0

	@micropython.native
	def Pool(self):
		while self.sm.rx_fifo() > 0 :
			r = self.sm.get()
			if r == 1: self.pos += 1
			else: self.pos -= 1

	def GetTurn(self):
		r = self.pos; self.pos = 0		
		return r
	
	def Clr(self): 
		self.pos = 0

	def Btn(self):
		# push = grnd (inverse value)
		return 0 == self.btn.value() 

if __name__ == "__main__":
	p1 = 32; bt = 40; sm = 10
	if True:
		rot = CLT1100(sm, p1, bt)
		lb = False
		while True:
			r = rot.GetTurn()
			if r: print(r,end = ' # ')
			if rot.Btn() != lb:
				print(f'Push:{rot.Btn()}',end = ' # ')
				lb = rot.Btn()
	else:
		# To help debug if PIO program is not working (test GPIO directly)
		A = Pin(p1, Pin.IN, Pin.PULL_UP)
		C = Pin(p1+1, Pin.IN, Pin.PULL_UP)
		v1 = 0
		while True:
			v2 = (A.value()<<1) + C.value()
			if v1 != v2:
				print(bin(v2)[2:], end = ' - ')
				v1 = v2


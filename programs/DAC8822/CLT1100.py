# ----------------------------------------------------
# pio code for CLT1100 rotary encoder
# -------------------------------------
machine.freq(200_000_000) 

# must run at 100MHz clock. 1 ns per clock
from rp2 import PIO, asm_pio, StateMachine
from machine import Pin, Timer
import time


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
		for p in CLT1100.POOL_LST: p["r"].Pool()
		# print('*', end='')

	@staticmethod
	def Register(info):
		CLT1100.POOL_LST.append(info)
		if len(CLT1100.POOL_LST) == 1:
			# setup timer irq
			CLT1100.TIMER = Timer(period=200, 
				mode=Timer.PERIODIC, callback=CLT1100.PoolEncoders)

	def __init__(self, smix, p1): # p1, p1+1: encoder A,C, p1+2: push 
		self.pos = 0
		Pin(p1,Pin.IN, Pin.PULL_UP)
		Pin(p1+1,Pin.IN, Pin.PULL_UP)
		self.sm = StateMachine(smix, _CLT1100, 5000, in_base=Pin(p1))
		self.sm.active(1)
		self.btn = Pin(p1+2, Pin.IN, Pin.PULL_UP)
		CLT1100.Register({"r":self,"bp":p1})
		# print(CLT1100.POOL_LST)

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
		return 0 == self.btn.value()

if __name__ == "__main__":	
	rot = CLT1100(0, 26)
	lb = False
	while True:
		r = rot.GetTurn()
		if r: print(r,end = ' # ')
		if rot.Btn() != lb:
			if rot.Btn(): print('Clk',end = ' # ')
			lb = rot.Btn()
		#print(f'{A.value()}{C.value()}{bt.value()}',end='~')

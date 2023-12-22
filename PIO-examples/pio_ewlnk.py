import time, rp2, array
from machine import Pin, Timer
import micropython

micropython.alloc_emergency_exception_buf(100)

_pio_ewl = None

# -----------------------------------------------
# pio code for ewlrf 1 clock = 10us
# -----------------------------------------------
@rp2.asm_pio(set_init=rp2.PIO.IN_HIGH, 
             in_shiftdir = rp2.PIO.SHIFT_LEFT,             
             fifo_join=rp2.PIO.JOIN_RX) 
def _ewlrf():    
    label("idle")
    #lo for at least 10 ms (max 11)
    set(x, 2)      # 3*30 loops 
    wait(0,pin,0)
    label("reloady")
    set(y, 29)
    label("10ms")
    jmp(pin, "idle")          # high too soon: wait next low transition
    jmp(y_dec,"10ms")    [9]  # 11 cycles * 30 * 3 * 10us = (9.9ms)
    jmp(x_dec,"reloady") [2]  # this adds 90us (9.99ms close enough)

    # low stayed for 10ms, check for too long
    set(x, 14)
    label("xtra1ms")
    jmp(pin, "start")         # valid start of message
    jmp(x_dec, "xtra1ms") [8] # 15 * 10 * 10us = 1.5ms
    jmp("idle") # too long, not a good start

    label("start")
    mov(isr,null)
    set(y, 23)  # read 24 bits

    label ("nxtbit")
    mov(x, 26)        # 27 * 5 clk * 10us = 1.35ms max high
    label("wait0")
    jmp(x_dec, "chk0")
    jmp("idle")         # stayed high too long, abort
    label("chk0")
    jmp(pin, "wait0") [2] # total 5 cycles per loop
    #wait(1,pin,0)
    #wait(0,pin,0)

    set(x, 15)   # 16 * 4 * 10us = 640us (mid point 675 - 50us lag of wait0)
    label ("0or1")
    jmp(pin, "shift_1")
    jmp(x_dec, "0or1") [2] # need 4 clks per loop

    # this is a 0: low for > 675us
    # verify not exceeding bit width (say 1.35ms: full bit)
    set(x, 14)
    label("0wide")
    jmp(pin, "shift_0") 
    jmp(x_dec, "0wide") [7] # 15*9*10us = 1.35ms
    jmp("idle") # bit too long, abort

    label("shift_0")
    set(x,0)
    jmp("shift_x")
    
    label("shift_1")
    set(x,1)
    
    label("shift_x")
    in_(x, 1)  # shift x (0 or 1) in isr
    jmp(y_dec,"nxtbit")
    push()
    irq(0)
    wrap()
    # wrap to push() when all bits (y) read

# only called when PIO FIFO has pending data
# only check validity or message, then store in circular buffer
@micropython.native
def Chk_ewl(no):
    while _pio_ewl.sm.rx_fifo() > 0:
        w1:int = _pio_ewl.sm.get(None, 0)
        # print(hex(w1), end = ' ')
        h = w1 & 0xFFFFF0
        b = 0
        # A = 8, B = 4, C = 2, D = 1
        if h == 0x4616E0: b = w1 & 15
        if h == 0xCBF020: b = ((w1 & 7) << 1) | ((w1 >> 3) & 1)

        if b == _pio_ewl.last_btn and time.ticks_ms() < _pio_ewl.expire:
            b = 0
            _pio_ewl.expire = time.ticks_ms() + 200 # prolong hold
        
        if b:
            # print(b, end = ' ')
            _pio_ewl.last_btn = b
            b |= (w1 >> 8) & 0xFF00 # high byte used as address
            _pio_ewl.expire = time.ticks_ms() + 200 # hold against repeat btn
            _pio_ewl.msgBuf[_pio_ewl.wrix] = b
            _pio_ewl.wrix += 1 # in viper this is quicker than (ix+1) % 32
            if _pio_ewl.wrix == ewlrf.MSG_BUF_SIZE: _pio_ewl.wrix = 0

# using 10 ms timer
@micropython.native
def PIO_ISR(pio):
    if _pio_ewl.sm.rx_fifo() > 0: # rx avail
        micropython.schedule(Chk_ewl, None)

class ewlrf(object):
    MSG_BUF_SIZE = 21
    def __init__(self, smix = 4, base_pin = 0):
        global _pio_ewl
        # create tx state machines
        self.wrix = 0
        self.rdix = 0
        self.msgBuf = array.array('H', x-x for x in range(0, 32))
        self.last_btn = 0
        self.expire = 0
        self.sm = rp2.StateMachine(smix, _ewlrf, freq=100000, # 1 clk = 10us
                                   in_base=Pin(base_pin, Pin.IN, Pin.PULL_UP),
                                   jmp_pin=Pin(base_pin))       

        _pio_ewl = self
        self.pirq = rp2.PIO(1).irq(PIO_ISR)

        self.sm.active(1)
    
    # returns a validated message from msgBuf circular, 32 messages
    # no protection for overrun, must read at acceptable pace
    def read(self):
        r = self.msgBuf[self.rdix]
        if r != 0:
            self.msgBuf[self.rdix] = 0
            self.rdix += 1
            if self.rdix == ewlrf.MSG_BUF_SIZE: self.rdix = 0
        return r

    # forced destructor (independent of ref counting)
    def stop(self):        
        self.sm.active(0)
        self.pirq = None
        rp2.PIO(1).remove_program()
        _pio_ewl = None        

    def __del__(self):        
        self.sm.active(0)
        self.pirq = None
        rp2.PIO(1).remove_program()
        print('Destructor called')

'''
# test it
tst = ewlrf()
cont = True
while cont:
    r = tst.read()
    if r:
        print(r, end = ' ')
        cont = r != 12
tst.stop()
tst = None
'''
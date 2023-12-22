import time, rp2, array
from machine import Pin, Timer
import micropython

micropython.alloc_emergency_exception_buf(100)

_pio_x10 = None

# -----------------------------------------------
# pio code for x10rf
# -----------------------------------------------
@rp2.asm_pio(set_init=rp2.PIO.IN_HIGH, 
             in_shiftdir = rp2.PIO.SHIFT_RIGHT,             
             fifo_join=rp2.PIO.JOIN_RX) 
def _x10rf():    
    label("idle")
    mov(osr, null)  # osr = 0. when -1: secutity (40 bits) msg done
    
    #hi for at least 8 ms (nominal n)
    set(x, 19)      # x = 22 to wait 9 ms (exception)
    label("h1")
    jmp(x_dec,"hi9") [12] # loops is 40 cycles * 20
    jmp("h2")        [12] # 80 clocks = 8ms
    label("hi9")
    jmp(pin,"h1")    [13]
    jmp("idle")
    
    #then lo for at least 4.2ms
    label("h2")
    mov(x, 20)
    wait(0,pin,0)
    label("lo4_5")
    jmp(pin, "idle")    [9] # 21 * 20 clocks = 4.2 ms
    jmp(x_dec, "lo4_5") [9]
    wait(1, pin, 0)     # about .3 ms
   
    # read bits
    label("rd_msg")  # lo pulse between 4 and 5.5 ms: read bits
    mov(isr,null)    # clr isr
    set(y, 31)       # 32 first bits (non security device)
    
    label("nxtbit")
    set(x, 11)       # mid point between 0.6ms and 1.7ms is 1.15    
    wait(0, pin, 0)  # wait end of start half bit
    
    label("time_0")          # if lo duration is < 1.15ms, its a zero
    jmp(pin, "shift_0") [8]  # lo end: set bit (y msb value)
    jmp(x_dec, "time_0")     # suppose 0 until we cross 1.15ms
    
    set(x, 13) # eom if lo > 2.6 ms (14 + 12 = 26)
    label("time_1")
    jmp(pin, "shift_1") [8]
    jmp(x_dec, "time_1")      # timeout = eom: push()
    
    wrap_target()
    push()
    set(y,15)          # extra security bits will eom before 10
    mov(x, osr)    
    jmp(x_dec, "idle") # message is max 2 push() osr=0, then -1 => done    
    mov(osr, x)    
    jmp("nxtbit")

    label("shift_0")
    set(x,0)
    jmp("shift_x")
    
    label("shift_1")
    set(x,1)
    
    label("shift_x")
    in_(x, 1)  # shift x (0 or 1) in isr
    jmp(y_dec,"nxtbit")
    irq(0)
    wrap()
    # wrap to push() when all bits (y) read


# only called when PIO FIFO has pending data
# only check validity or message, then store in circular buffer
@micropython.native
def Chk_X10(no):
    w1:int = _pio_x10.sm.get(None, 0)
    w2:int = w1 >> 16
    w1 &= 0xFFFF 
    # print(hex(w1),'-',hex(w2))
    if (w2 & 0xFF) == ((w2 >> 8) ^ 0xFF):
        add:bool = False
        if (w1 & 0xFF) == ((w1 >> 8) ^ 0xFF): # standard x10
            _pio_x10.sm.get(None, 0)
            #_pio_x10.msgBuf[_pio_x10.wrix] = (w1 & 0xFF00) | (w2 >> 8)
            _pio_x10.msgBuf[_pio_x10.wrix] = ((w1 & 0xFF) << 8) | (w2 & 0xFF)
            add = True
        elif ((w1 >> 8) ^ 0xF0) == (w1 & 0xFF): # alarm sytem device
            xtra:int = _pio_x10.sm.get(None, 0)
            addr:int = (xtra >> 8) & 0xFF0000
            pb: int = (xtra >> 23) & 1
            pv: int = 0 # calculate parity
            i:int = 0
            while i<8: 
                if (xtra & 0x80000000): pv ^= 1 # toggle for each '1'
                xtra <<= 1
                i += 1            
            if pb == pv: # good parity (discard msg otherwise)                
                _pio_x10.msgBuf[_pio_x10.wrix] = \
                    ((w1 & 0xFF) << 8) | (w2 & 0xFF) | addr | 0x80000000
                add = True
        if add:
            # print(hex(_pio_x10.msgBuf[_pio_x10.wrix]))
            _pio_x10.wrix += 1 # in viper this is quicker than (ix+1) % 32
            if _pio_x10.wrix == X10rf.MSG_BUF_SIZE: _pio_x10.wrix = 0

# using 10 ms timer
@micropython.native
def PIO_ISR(pio):
    if _pio_x10.sm.rx_fifo() >= 2: # rx avail
        micropython.schedule(Chk_X10, None)

class X10rf(object):
    MSG_BUF_SIZE = 21
    def __init__(self, smix = 0, base_pin = 6):
        global _pio_x10
        # create tx state machines
        self.wrix = 0
        self.rdix = 0
        self.msgBuf = array.array('L', x-x for x in range(0, 32))
        self.sm = rp2.StateMachine(smix, _x10rf, freq=100000, # 100 clk = 1ms
                                   in_base=Pin(base_pin, Pin.IN, Pin.PULL_UP),
                                   jmp_pin=Pin(base_pin))       

        _pio_x10 = self
        self.pirq = rp2.PIO(0).irq(PIO_ISR)
        self.sm.active(1)
    
    # returns a validated message from msgBuf circular, 32 messages
    # no protection for overrun, must read at acceptable pace
    def read(self):
        r = self.msgBuf[self.rdix]
        if r != 0:
            self.msgBuf[self.rdix] = 0
            self.rdix += 1
            if self.rdix == X10rf.MSG_BUF_SIZE: self.rdix = 0
        return r

    def stop(self):
        self.sm.active(0)
        self.pirq = None
        rp2.PIO(0).remove_program()
        _pio_x10 = None

    def __del__(self):
        self.tim.deinit()
        self.sm.active(0)
        _pio_x10 = None

'''
# test it
tst = X10rf()
r = 0
while r != 2308:
    r = tst.read()
    if r: print(r, end = ' ')
    else: time.sleep_ms(100)
tst.stop()
'''
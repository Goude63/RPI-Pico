import time, rp2
from machine import Pin

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
    wrap()
    # wrap to push() when all bits (y) read

class X10rf(object):
    def __init__(self, smix = 0, base_pin = 15):
        # create tx state machines
        self.sm = rp2.StateMachine(smix, _x10rf, freq=100000, # 100 clk = 1ms
                                   in_base=Pin(base_pin, Pin.IN, Pin.PULL_UP),
                                   jmp_pin=Pin(base_pin))                                   
        self.sm.active(1)
    
    # returns a 8 bits integer if cnt=1, a string otherwise
    def read(self):
        return self.sm.get(None, 0)

    def rx_avail(self):        
        return (self.sm.rx_fifo())

    def __del__(self):
        self.sm.active(0)        

#test tx. See "test_uarts.py" for complete tx/rx test
tst=X10rf()
while True: print(hex(tst.read()))
#while True:
#    tst.send(0, "A Z X H ") #x41)  # remember uart = lsb first (on scope...)


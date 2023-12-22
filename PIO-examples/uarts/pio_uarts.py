import time, rp2
from machine import Pin

# -------------------------------------
# pio code for tx (5 instructions)
# -------------------------------------
@rp2.asm_pio(out_init=rp2.PIO.OUT_HIGH,
             set_init=rp2.PIO.OUT_HIGH,
             autopull=False,
             pull_thresh=8,
             out_shiftdir = rp2.PIO.SHIFT_RIGHT,
             fifo_join=rp2.PIO.JOIN_TX)
def _uart_tx():
    wrap_target()
    pull(block)        # pull takes a value from tx fifo into osr
    set(pins, 0) [1]   # start bit (2 clocks)
    label("sh")     
    out(pins,1)	       # output one bit
    jmp(not_osre,"sh") # with the jump, we have 2 clocks per bits
    set(pins,1)  [1]   # stop bit / bus to idle (two clocks)
    wrap()

# -------------------------------------
# pio code for rx. 8 clocks = 1 bit
# 6 instructions :)
# -------------------------------------
@rp2.asm_pio(set_init=rp2.PIO.IN_HIGH, autopush=False,
             push_thresh=8,
             in_shiftdir = rp2.PIO.SHIFT_RIGHT,
             fifo_join=rp2.PIO.JOIN_RX)
def _uart_rx():
    wrap_target()
    wait(0, pin, 0)   # wait for start bit (1 clock)
    set(x, 7) [9]     # allow 1/2 clock to detect start bit. total 11 clocks
    label("nxt")     
    in_(pins, 1) [6]  # read one bit wait 7 clocks
    jmp(x_dec, "nxt") # with the jump, we have 8 clocks per bits
    push() [5]        # push byte and wait for middle of stop bit 
    wait(1, pin, 0)   # Confirm stop bit (helps resync if bad framing)
    wrap()

class Uarts(object):
    # baud and buf_size 
    def __init__(self, base_pin = 4, baud = 9600, buf_size = 64):
        if type(baud) != type([]): tmp = []; tmp.append(baud); baud = tmp
        if type(buf_size) != type([]): tmp = []; tmp.append(buf_size); buf_size = tmp            
        self.ch_cnt = max(len(baud), len(buf_size))
        while len(baud) < self.ch_cnt: baud.append(9600) # use default for missing vals
        while len(buf_size) < self.ch_cnt: buf_size.append(64)
        
        # create tx state machines
        self.smtx = []
        for x in range(self.ch_cnt):
            self.smtx.append(rp2.StateMachine(2*x, _uart_tx, freq=2*baud[x],
                                              out_base=Pin(base_pin + 2*x),
                                              set_base=Pin(base_pin + 2*x)))
            self.smtx[x].active(1)

        #create rx state machines
        self.smrx = []
        for x in range(self.ch_cnt):            
            self.smrx.append(rp2.StateMachine(2*x+1, _uart_rx, freq=8*baud[x],
                                              in_base=Pin(base_pin + 2*x + 1)))
            self.smrx[x].active(1)

    def send(self, ch, data):  # data can be a byte, a string, a byte array...
        self.smtx[ch].put(data, 0)
    
    def tx_avail(self, ch):
        return (8 - self.smtx[ch].tx_fifo())
    
    # returns a 8 bits integer if cnt=1, a string otherwise
    def read(self, ch, cnt = 1):
        if cnt == 1: return self.smrx[ch].get(None, 24)
        r = ''
        for n in range(cnt): r = r + chr(self.smrx[ch].get(None, 24))
        return r

    def rx_avail(self, ch):        
        return (self.smrx[ch].rx_fifo())

    def __del__(self):
        for sm in self.smtx: self.smtx.active(0)
        for sm in self.smrx: self.smrx.active(0)

#test tx. See "test_uarts.py" for complete tx/rx test
#tst=Uarts(base_pin = 16, baud=460800)
#while True:
#    tst.send(0, "A Z X H ") #x41)  # remember uart = lsb first (on scope...)


import time, rp2, array
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
    pull(block)        # pull takes a value from tx fifo into osr
    set(pins, 0) [1]   # start bit (2 clocks)
    label("sh")     
    out(pins,1)	        # output one bit
    jmp(not_osre,"sh")  # with the jump, we have 2 clocks per bits
    set(pins,1)  [0]    # 1 stop bits / bus to idle. Two clocks including pull() on wrap

# -------------------------------------
# pio code for rx. 8 clocks = 1 bit
# 6 instructions :)
# -------------------------------------
@rp2.asm_pio(set_init=rp2.PIO.IN_HIGH, autopush=False,
             push_thresh=8,
             in_shiftdir = rp2.PIO.SHIFT_RIGHT,
             fifo_join=rp2.PIO.JOIN_RX)
def _uart_rx():
    wait(1, pin, 0)   # Wait idle state
    wait(0, pin, 0)   # wait for start bit (1 clock)
    set(x, 7) [9]     # allow 1/2 clock to detect start bit. total 11 clocks
    label("nxt")     
    in_(pins, 1) [6]  # read one bit wait 7 clocks
    jmp(x_dec, "nxt") # with the jump, we have 8 clocks per bits
    push()            # push byte we are now in middle of stop bit 

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
    
    # returns a bytearray
    def read(self, ch, cnt = None,
             offset = 0, buff = None):
        if cnt is None: cnt = self.rx_avail(ch)
        if buff is None: r = bytearray(cnt + offset)
        else: r = buff        
        t = 0
        while t < cnt:
            n = self.rx_avail(ch)
            if n == 0: time.sleep_us(200)
            else:
                r[t + offset] = self.smrx[ch].get(None, 24)
                t += 1
        if buff is None: return r

    def rx_avail(self, ch):        
        return (self.smrx[ch].rx_fifo())

    def __del__(self):
        for sm in self.smtx: self.smtx.active(0)
        for sm in self.smrx: self.smrx.active(0)

#test tx. See "test_uarts.py" for complete tx/rx test
#tst=Uarts(base_pin = 16, baud=10000)
#while True:
    #tst.send(0, b"\x18\x24\x42") #x41)  # remember uart = lsb first (on scope...)
    #tst.send(0, b"\x00") #x41)  # remember uart = lsb first (on scope...)


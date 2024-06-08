import time, rp2, array, math, machine
from machine import Pin

# ---------------------------------------------------
# inspired by Toby Roberts pwm example in github
# but: improved 100% situation + added multi-channel
# ---------------------------------------------------
@rp2.asm_pio(out_init=rp2.PIO.OUT_LOW,
             sideset_init=rp2.PIO.OUT_LOW,
             in_shiftdir = rp2.PIO.SHIFT_LEFT,
             fifo_join=rp2.PIO.JOIN_TX) 
def _pwm():
    mov(x,isr)     # default pulse duration = isr => 0% (isr loaded with exe in __init__)
    wrap_target() 
    label("idle")    
    pull(noblock)  # pull "on" duration (osr=x when fifo empty)
    mov(x, osr)    # save default value in x
    mov(y, isr)    # y = total pulse duration
    jmp(x_not_y, "normal") 
    jmp("idle").side(1)   # handle 100% on case (set out = 1)

    label("normal")
    nop().side(0)
    label("loop")
    jmp(x_not_y, "skip")
    nop().side(1)
    label("skip")
    jmp(y_dec, "loop")

class PWM(object):
    # res (resolution) is total number of steps in one pulse. f is pulses' frequency
    # use arrays for res/f to create up to 4 pwm channels
    # pf is the pulse frequency (pulses per second) 1 MHz by default
    # the internal sm frequency is 2 * res * pf
    def __init__(self, base_pin = 16, res = 100, pf = 1000000):
        machine.freq(270000000)
        if type(res) != type([]): tmp = []; tmp.append(res); res = tmp
        if type(pf) != type([]): tmp = []; tmp.append(pf); pf = tmp 
        self.ch_cnt = min(max(len(pf), len(res)), 4)
        while len(res) < self.ch_cnt: res.append(100) # use default for missing vals
        while len(pf) < self.ch_cnt: pf.append(1000)
        self.pf = pf
        self.res = res
        
        # create pwm state machines. Use successive io pins for multi channel
        self.sm = []
        for x in range(self.ch_cnt):
            self.sm.append(rp2.StateMachine(x, _pwm, freq=2*self.pf[x] * self.res[x],
                                            sideset_base=Pin(base_pin + x),
                                            set_base=Pin(base_pin + x)))
            self.sm[x].put(self.res[x]-1)  # set 100% pulse width
            self.sm[x].exec("pull()")
            self.sm[x].exec("mov(isr, osr)") # full width len stored in isr
            self.sm[x].active(1)

    # vals are values between 0 and self.res[ch] (0-100 when using def init values
    # a single value or an array can be used for vals (for low jitter use an array)
    # rep > 1 ony makes sense for arrays since the state machine repeats the last ratio forever
    def send(self, ch, vals, rep=1):  
        for n in range(rep): self.sm[ch].put(vals, 0)
        
    # shape = "sin", "saw" or "tri".  wf is waveform frequency in hz
    # the function generates one cycle. use rep value in send method to output many cycles
    def wav(self, ch = 0, shape = "sin", wf=2000):
        cnt = (self.pf[ch] // wf) - 3  # sample cnt per cycle (-3 for PIO overhead)
        r = array.array("H",[])
        a = (self.res[ch] // 2) - 1 # limit = res - 1
        d = (2*math.pi)/cnt
        if shape == "tri": cnt = cnt // 2
        for i in range(cnt):
            if   shape == "sin": y = a + int(a * math.sin(i * d)) # y in [0..res-1]
            else: y = int(2 * a * ( i / cnt)) # saw and tri            
            r.append(y)
        if shape == "tri":
            for i in range(cnt): r.append(r[cnt-i-1])
        return r
    

    def __del__(self):
        for sm in self.sm: self.sm.active(0)


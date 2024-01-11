from machine import Pin, PWM

class LED(object):
    def __init__(self, neo = True, led_io = None):
        self.neo = neo
        if neo:
            import neopixel
            if not led_io: led_io = 16 # default for Neo Pixel on Wave Share Zero
            self.pixel = neopixel.NeoPixel(Pin(led_io), 1)
        else:
            if not led_io:led_io = 25
            #self.led = Pin(led_pin, Pin.OUT)
            self.pwm = PWM(Pin(led_io))
            self.pwm.freq(1000)
            self.pwm.duty_u16(0)

    def on(self, r:int=128, g:int=128, b:int=128):
        if self.neo:
            self.pixel[0] =(r, g, b)
            self.pixel.write()
        else:            
            self.pwm.duty_u16((r+g+b) * 85)
            #v = 1 if r+g+b>100 else 0
            #self.led.value(v)

    def off(self):
        if self.neo:
            self.pixel[0] =(0,0,0)
            self.pixel.write()
        else:
            self.pwm.duty_u16(0)
            #self.led.value(0)
    
'''
#tst it 
import time
led = LED()
r,g,b = (0,0,0)
while True:
    led.on(r,g,b)
    r += 16
    if r>255: r=0; g += 16
    if g>255: g=0; b += 16
    if b>255: b = 0
    time.sleep_ms(20)
'''

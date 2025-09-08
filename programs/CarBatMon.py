import time
from machine import Pin

machine.freq(48000000)

SCRATCH =  0x40058000 + 0x20
MAGIC = 12345
DS_MS = 5 * 60 * 1000 # 1=>5 for 5 min

# used to convert Adc val to 12V input (correct for Adc and resistor divider)
#  +in - 97k - adc input - 9.3k - grnd in (divider allows for up to 25V batt in)
X1=748; Y1=7.08; X2=2354; Y2=20.1  # X: Adc values, Y: Vin values
M = (Y2-Y1) / (X2-X1)  # calculating y=mx+b parameters for adc=vin line
B = Y2 - M * X2

def avgarr(arr):
    if arr and len(arr):
        return sum(arr)/len(arr)
    else:
        return 0

# log value and RTC time when debugging
def LogValue(s):
    f = open('data.txt', 'a')
    f.write(s + '\r\n')
    f.close()

led = Pin('LED', Pin.OUT, value=0)
led.on()
goio = Pin(16, Pin.IN, Pin.PULL_UP)  # true when NOT debugging

r = machine.reset_cause()
s = machine.mem32[SCRATCH]
print(r, s, goio())
LogValue("{:1d} ".format(r) + "{:1d} ".format(s) + "{:1d} ".format(goio()))

if (r == machine.WDT_RESET) and (s == MAGIC) and goio():
    # print('Request for deepsleep')    
    for n in range(5): led.on(); time.sleep_ms(50); led.off(); time.sleep_ms(50)
    machine.mem32[SCRATCH] = 0
    machine.deepsleep(DS_MS)
    machine.reset() 

else:
    # print('Normal sequence')

    from adc import Adc
    adc = Adc(chs=0, fs=20)

    while True: # in debug mode, infinite loop instead of sleep
        # do the voltage measurment here

        led.on()
        avg = avgarr(adc.Read(40))
        led.off()

        vin = avg * M + B
        print('Battery voltage=',vin)
        intv = int(round(vin*100))
        scnt = machine.mem32[SCRATCH + 8] + 1  # force log counter

        if ((abs(intv - machine.mem32[SCRATCH + 4])>10) or (scnt >= 4)):  # force every 4 wake-ups
            # transmit new value to logger
            print ('new value logged:', intv/100)
            LogValue("{:2.2f}".format(vin))  # TBD also transmitt udp message to logger
            machine.mem32[SCRATCH + 4] = intv
            scnt = 0
        machine.mem32[SCRATCH + 8] = scnt

        # in non debug, this will exit the infinite loop
        if goio():
            # deep sleep and reset
            machine.mem32[SCRATCH] = MAGIC # request deep sleep 
            machine.reset()
        else: 
            # no deepsleep in debug
            for n in range(1000): time.sleep_ms(10) # allows for break 

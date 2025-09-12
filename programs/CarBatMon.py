import time, gc, os
from machine import Pin
from wifi import WiFi

# machine.freq(48000000)
machine.freq(100000000)

SCRATCH =  0x40058000 + 0x20
MAGIC = 12345
DS_MS = 1 * 60 * 1000 # 1=>5 for 5 min

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

# useful when debugging issues only occuring far far away
logcnt = 0 # semi static variable...
def LogToFile(s, end = '\r\n'):
    global logcnt
    lf = 'log.txt'
    logcnt += 1
    if logcnt >= 500: # check log file size every 500 logs
        logcnt = 0
        if os.stat(lf)[6] > 100000:  # delete after 100kb
            os.remove(lf)

    f = open(lf, 'a')
    f.write(s + end)
    f.close()

# log value and RTC time when debugging
def LogValue(v):
    loggers = [188, 204, 200 ]

    # log on network
    gc.collect()
    wifi= WiFi('PicoLogCarBat','CA','cell')
    wifi.Connect('marc', 'bonjourlapolice')  # will make up to 30 attempts
    wifi.DoLog(f'rssi={wifi.rssi()} dBm')

    # if cannot connect reset and retry
    if wifi.status() != 3: 
        LogToFile('Did not connect')
        machine.mem32[SCRATCH + 4] = 0 # force log again
        if goio(): machine.reset()
        else: print('no wifi'); return
    else:
        LogToFile('Wifi connected')
    
    # log into the file (only if )
    fv = "{:2.2f}".format(v)
    LogToFile(f'Logged Voltage: {fv}')

    # log voltage on all loggers
    for ad4 in loggers:
        fa = f'http://192.168.1.{ad4}:8889/Eg4?+AutoBat={fv}'
        r = wifi.get(fa)
        if r[-1:] == '0': 
            wifi.DoLog(f'x{ad4}')
            # wifi.DoLog(f'Unable to log var on:\r\n{fa}')
            time.sleep(1)
    
    # log on UDP terminal debugger
    wifi.DoLog(f'New voltage:{fv}\r\n')
    time.sleep(1)
    wifi.disconnect() # for debug mode (otherwise we reboot)

try:
    led = Pin('LED', Pin.OUT, value=1)
    time.sleep(1)
    goio = Pin(16, Pin.IN, Pin.PULL_UP)  # true when NOT debugging

    r = machine.reset_cause()
    s = machine.mem32[SCRATCH]
    print(r, s, goio())
    LogToFile(f'{r}, {s}, {goio()}')

    if (r == machine.WDT_RESET) and (s == MAGIC) and goio():
        # print('Request for deepsleep')
        LogToFile('Going to deepsleep')
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
            LogToFile('Read ADC')
            avg = avgarr(adc.Read(40))
            led.off()

            vin = avg * M + B
            LogToFile(f'Raw voltage: {vin}')
            print('Raw voltage=',vin)
            intv = int(round(vin*100))
            scnt = machine.mem32[SCRATCH + 8] + 1  # force log counter

            if ((abs(intv - machine.mem32[SCRATCH + 4])>10) or (scnt >= 4)):  # force every 4 wake-ups
                # transmit new value to logger
                print ('new value logged:', intv/100)
                machine.mem32[SCRATCH + 4] = intv  # store voltage to reduce logs
                LogValue(vin) 
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
except Exception as e:
    msg = f"Unexpected error: {e}"
    print(msg)
    LogToFile(msg)

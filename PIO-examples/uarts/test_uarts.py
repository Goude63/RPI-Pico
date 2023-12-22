#test 4 uart channels (PIO programmed) using pio_uarts library
#needs loopback jumpers on pins 19-20, 21-22, 24-25 and 26-27
from pio_uarts import Uarts
import random

machine.freq(250000000)
tx_siz = 4
form = '{:0' + str(tx_siz) + 'd}'

#setup predictable random number table (validate rx = tx)
random.seed()
rndvals = []
rnd_size = 512
for ix in range(rnd_size):rndvals.append(random.randrange(10**tx_siz-1))
tx_ix = [0, 137, 295, 421]
rx_ix = [0, 137, 295, 421]
pass_cnt = [0, 0, 0, 0]
fail_cnt = [0, 0, 0, 0]

u = Uarts(base_pin=14, baud=[230400, 115200, 430800, 861600])

i=0
while True:
    for ch in range(4):
        if u.tx_avail(ch) >= tx_siz :
            i = i + 1
            u.send(ch, form.format(rndvals[tx_ix[ch]]))
            tx_ix[ch] = (tx_ix[ch] + 1) % rnd_size

        while u.rx_avail(ch) >= tx_siz:
            v = u.read(ch, tx_siz)
            
            if v == form.format(rndvals[rx_ix[ch]]):
                pass_cnt[ch] = pass_cnt[ch] + tx_siz
                rx_ix[ch] = (rx_ix[ch] + 1) % rnd_size
            else :
                fail_cnt[ch] = fail_cnt[ch] + tx_siz
                while u.rx_avail(ch) > 0: u.read(ch)  # flush tx buffer 
                rx_ix[ch] = tx_ix[ch] # re-sync random sequence           
            
    if i >= 2000:
        print("Pass cnt=", pass_cnt, "   Fail cnt = ", fail_cnt)
        i = 0

# Pass cnt= [14356500, 14356500, 14356500, 14356500]    Fail cnt =  [0, 0, 0, 0]
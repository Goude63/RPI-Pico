from ST7735 import TFT
from CLT1100 import CLT1100
from f_sys import f_sys
from f_cp437_8x8 import f_cp437_8x8
from f_lcd5x7 import f_lcd5x7
from f_10x14 import f_10x14
from f_6x8 import f_6x8
from f_3x5 import f_3x5

from machine import SPI,Pin

# pins for WeAct module DAC8822 dev box 
spi = SPI(0, baudrate=machine.freq()//2, polarity=0, phase=0, sck=Pin(2), mosi=Pin(3), miso=None)
tft = TFT(spi,4,5,6,46) # REG, RST, /CS, LED

tft.initr()
tft.rotation(1); tft.rgb(True); tft.fill(); tft.led(75)

flst = [f_3x5, f_sys, f_cp437_8x8, f_lcd5x7, f_6x8, f_10x14]

y = 0
for fnt in flst:
	tft.text((0,y),  '158!"#$&abglAZ_',  tft.WHITE, fnt) 
	y += fnt['Height'] + 2

y += 10
tft.text((0,y),  '~!@#$%^&*()-_=+[]\{\};:\'" abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ',  tft.WHITE, f_lcd5x7, nowrap=False) 





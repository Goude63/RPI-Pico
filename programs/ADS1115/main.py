from ADS1115 import *
from usbcom import USBCOM
from machine import Pin, ADC
import time,json
import st7789, tft_config
import tft_buttons as Buttons
# import vga1_8x16 as font
import romancs as font


FIX_X  = -20
FIX_Y  = 0
MAXX   = 284
SPH    = 3600
PUSHED   = 0
RELEASED = 1
RED    = st7789.color565(255,127,127)
ORANGE = st7789.color565(255,191,191)
BLUE   = st7789.color565(127,127,255)
GREEN  = st7789.color565(127,255,127)
GREY   = st7789.color565(191,191,191)
BLACK  = st7789.BLACK

RNGV = (0.256, 0.512, 1.024, 2.048, 4.096, 6.144)
MName = ['R1','Par', 'Ser']
KeyTrack = {"Last":-1, "n":0, "Max":0}

# module level "globals"
usb = USBCOM()
ads = ADS1115(i2c_id = 1, sda=Pin(18), scl=Pin(19))
adc = ADC(27)
tft = tft_config.config(3)
btns = Buttons.Buttons()


cfg = {
	"Mode" : 0,	"R":[0.21627314239740, 0.10751858502626, 0.43486739695072], "Range":5,
}

state = {
	"V" : 0 ,"A" : 0, "Ah" : 0, "Wh" : 0, "Graph": [] 
}
def ProcessMessages():
	msg=usb.Scan().lower()
	if (msg): 
		if (msg[0:10]=='set_range='):
			r = int(msg[10:])
			if (0<=r<=5):
				cfg["Range"] = r 
				DisplayCfg()
				ads.setVoltageRange_mV(ADS1115_RNG[r])
				print('Range set to ix',r)
				
	return msg

def SaveCfg():
	with open("config.json", "w") as f:
		json.dump(cfg, f)

def LoadCfg():
	try:
		with open("config.json", "r") as f:
			cfg = json.load(f)
	except:
		SaveCfg()

# Temperature cleanup code 
# rel tolerance: relative average to be exluded when n >= 10
@micropython.native
def ReadTemp(n=200, tol = 0.05): 
	tot = 0
	for i in range(n):
		t = 3.3 * adc.read_u16()/65536
		t = (t / 0.005) - 273.15
		tot += t

	avg = tot / n
	# Redo but this time exclude outliers
	if (n>=10):
		tot = 0
		cnt = 0
		for i in range(n):
			t = 3.3 * adc.read_u16()/65536
			t = (t / 0.005) - 273.15

			if (abs(t - avg)/avg < tol):
				tot += t
				cnt += 1
		if (cnt>0):
			avg = tot/cnt

	return avg

def Display(x, y, text, fg = st7789.WHITE, bg = st7789.BLACK,  sc = 1.5):
	if not isinstance(text, str): text = str(text)	
	w =  tft.draw_len(font, text, sc)
	if x < 0: x = MAXX - w + x
	h = round(font.HEIGHT * sc)
	tft.draw(font, text, x, y, fg, sc )

def DisplayTop():
	h = int(round(font.HEIGHT * 1.5))
	y = 2

	tft.fill_rect(0, y+6, MAXX//2, h, st7789.BLACK)
	Display(5, y+20, f'{state["V"]:.3f}V', fg=RED)

	tft.fill_rect(MAXX//2+1, y+6, MAXX//2, h, st7789.BLACK)
	Display(-26, y+20, f'{state["A"]:.2f}A', fg=BLUE)

	y = 30
	tft.fill_rect(0, y+6, MAXX//2, h, st7789.BLACK)
	v = state["Wh"]
	fv =f'{v:.2f}Wh' if v<10 else f'{v:.0f}Wh'
	Display(5, y+20, fv, fg=ORANGE)

	v = state["Ah"]
	fv =f'{v:.2f}Ah' if v<10 else f'{v:.1f}Ah'
	tft.fill_rect(MAXX//2+1, y+6, MAXX//2, h, st7789.BLACK)
	Display(-1, y+20, fv, fg=GREEN)

def DisplayCfg():
	tft.fill_rect(0, 210, MAXX, font.HEIGHT, st7789.BLACK)
	Display(1, 220, f'Mode:{MName[cfg["Mode"]]}', fg=GREY, sc=1)
	Display(MAXX//2, 220, f'Range:{RNGV[cfg['Range']]}', fg=GREY, sc=1)

@micropython.native
def Cumulate(vals, dt):
	vrix = 1 if cfg["Mode"] == 2 else 0  # R1 or RP: ix = 0, RS: ix = 1
	v = vals[2]
	r = cfg["R"][cfg["Mode"]]
	vr = vals[vrix] 
	i = max(0, vr / r)
	dt /= SPH  #  dt in hours
	state["A"] = i
	state["V"] = v
	state["Ah"] += i * dt
	state["Wh"] += v * i * dt

def ExecBtnPress(Keys):
	#tft.fill_rect(100, 100, 200, 30, st7789.BLACK)
	#Display(100,120,f'{Keys:04b}')
	if Keys == 2 or Keys == 8:
		d = 1 if Keys == 2 else -1
		cfg["Range"] += d
		if cfg["Range"]>5: cfg["Range"] = 5 
		if cfg["Range"]<0: cfg["Range"] = 0
		DisplayCfg()
		ads.setVoltageRange_mV(ADS1115_RNG[cfg["Range"]])

	if Keys == 1 or Keys == 4:
		d = 1 if Keys == 1 else -1
		cfg["Mode"] += d
		if cfg["Mode"]>2: cfg["Mode"] = 0 
		if cfg["Mode"]<0: cfg["Mode"] = 2
		DisplayCfg()
	if Keys == 3:
		SaveCfg()
	if Keys == 10:
		state["Ah"] = 0
		state["Wh"] = 0

def CheckKeys():	
	Keys = btns.key1.value() + (btns.key2.value() << 1) + (btns.key3.value() << 2) + (btns.key4.value() << 3)
	Keys ^= 0xF

	# actions are on release to allow multi button press
	if Keys == 0:
		if (KeyTrack["n"]>10):  # do action
			ExecBtnPress(KeyTrack["Last"]) 		
		KeyTrack["n"] = 0
		KeyTrack["Last"] = 0
	elif Keys>KeyTrack["Last"]:
		KeyTrack["Last"] = Keys
		KeyTrack["n"] = 0
	elif Keys > 0 and Keys == KeyTrack["Last"]:
		KeyTrack["n"] += 1

# @micropython.native # comment when debugging to get error line numbers
def main():
	tft.init()
	tft.fill(st7789.BLACK)

	LoadCfg()
	DisplayCfg()

	# tst()

	Avg_Cnt = 64
	delay = 2000000

	machine.freq(250000000)
	ads.setAvgCNt(Avg_Cnt)
	ads.setVoltageRange_mV(ADS1115_RNG[cfg["Range"]])
	ads.setConvRate(ADS1115_250_SPS)

	Chnls = (0, 1, 7) # AIN0, AIN1, AIN0-AIN1 (R1, R1+R2, V)
	t0 = time.ticks_us()

	while(True):
		DisplayTop()
		while time.ticks_diff(time.ticks_us(), t0) < delay:
			ProcessMessages()
			CheckKeys()
			time.sleep_ms(10)

		t1 = time.ticks_us()
		dt = time.ticks_diff(t1, t0) / 1000000
		t0 = t1

		rt = round(ReadTemp(),1) # resistance temperature
		vals = ads.readMulti(Chnls) 
		print(vals + (rt,))
		Cumulate(vals, dt)	
				
main()
machine.freq(160_000_000)
from ADS1115 import *
from usbcom import USBCOM
from machine import Pin, ADC
import time,json
import st7789, tft_config
import tft_buttons as Buttons
import romancs as font
import array, json, gc

VERSION = "1.33"
FIX_X  = -20
FIX_Y  = 0
MAXX   = 320   # must be even
SPH    = 3600
PUSHED   = 0
RELEASED = 1
RED    = st7789.color565(255,127,127)
ORANGE = st7789.color565(255,191,191)
BLUE   = st7789.color565(127,127,255)
AUTOSC = st7789.color565(128,32,32)
GREEN  = st7789.color565(127,255,127)
DGREEN = st7789.color565(0,128,0)
GREY   = st7789.color565(191,191,191)
BLACK  = st7789.BLACK

RNGV = (0.256, 0.512, 1.024, 2.048, 4.096, 6.144)
MName = ['R1','Parallel', 'Serial']
KeyTrack = {"Last":-1, "n":0, "Max":0, "Long":False}
FanMsgCnt = 0

# module level "globals"
usb   = USBCOM()
ads   = ADS1115(i2c_id = 1, sda=Pin(18), scl=Pin(19))
adc   = ADC(27)
relay = Pin(5,Pin.OUT,value=0)
tft   = tft_config.config(3)
btns  = Buttons.Buttons()
SMODES  = ("LiPo","LiFePo4")
SLIMITS = ([0.3, 3.2, 4.2], [0.5, 3.0, 3.6]) # auto off limits (work A, minv, maxv)

cfg   = {"Mode" : 0,	"R":[0.197684, 0.111008, 0.396938], "Range":5, "SMode":0,
		  "AutoScale":1, "VScale":[3.0, 3.7], "IScale": [4.0, 15.0] }

state = {"V" : 0 ,"A" : 0, "Ah" : 0, "Wh" : 0, "T":0}
display = {"Error": 0, "Pause": 0, "Splash": 0, "RelayDelay": 0, "ErrMsg":[]}

Graph = {"Varr": array.array('f',[0] * MAXX), "Iarr": array.array('f',[0] * MAXX), 
	 "Xix" : 0, "PtPerPix": 1, "n": 0 , "y0":80, "h":100}

def InitGraph(ix = 0):
	Graph["Varr"][ix] = 0
	Graph["Iarr"][ix] = 0
	Graph["Xix"] = ix
	Graph["n"] = 0
	if ix==0: Graph["PtPerPix"] = 1 # when we clear everything

@micropython.native
def DrawGraphPixel(x1,g,c):
	n = g + "arr"
	s = cfg[g + "Scale"]
	y1 = Graph[n][x1]
	y0 = y1 if x1==0 else Graph[n][x1-1]
	if not s[0]<y0<s[1]: y0 = y1
	x0 = max(0,x1)

	if s[0]<y1<s[1]:
		y1 = Graph["y0"] + Graph["h"] - round(Graph["h"] * (y1 - s[0]) / (s[1]-s[0]))
		y0 = Graph["y0"] + Graph["h"] - round(Graph["h"] * (y0 - s[0]) / (s[1]-s[0]))
		tft.line(x0,y0,x1,y1,c)

def RedrawGraph():
	y = Graph["y0"]+4
	tft.fill_rect(0, y-5, MAXX, Graph["h"] + 23  , BLACK)
	# tft.rect(0, y-5, MAXX, Graph["h"] + 23  , st7789.WHITE)
	Display(-1,y, round(cfg["VScale"][1],1), sc=0.75, fg=RED)
	Display(-1,y+Graph["h"]+8, round(cfg["VScale"][0],1), sc=0.75, fg=RED)
	Display(0,y, round(cfg["IScale"][1],1), sc=0.75, fg=BLUE)
	Display(0,y+Graph["h"]+8, round(cfg["IScale"][0],1), sc=0.75, fg=BLUE)
	if cfg["AutoScale"]:
		tft.rotation(0)		
		Display(y+Graph["h"]//2 - 30, 10, '- auto -', sc=0.6, fg=AUTOSC)
		tft.rotation(3)
	for ix in range(Graph["Xix"]):
		DrawGraphPixel(ix, "V", RED)
		DrawGraphPixel(ix, "I", BLUE)
	
	# re-show error message if graph is redrawn (in case there is an error pending)
	if display["Error"]: ShowError(display["ErrMsg"])

def AutoScale(g, v):
	if cfg["AutoScale"] == 0: return # autoscale off
	g = g.upper()
	n = Graph["Xix"]

	# set scale for new blank graph (first point)
	if n == 0:
		chng = True
		if abs(v)<=0.5:
			cfg[g+"Scale"] = [0,0.1]
		else:
			cfg[g+"Scale"] = [v * 0.8, v * 1.2]
	else:
		chng = True
		rng = cfg[g+"Scale"]
		if v > rng[1]: 
			rng[1] = (v - rng[0]) * 1.2 + rng[0]
		elif v > 0 and v < rng[0]: 
			rng[0] = rng[1] - (rng[1] - v) * 1.2
		else: chng = False

	if chng: RedrawGraph() # re-draw with new scaling

@micropython.native
def GraphAddPt(v,i):
	xix = Graph["Xix"]
	Graph["Varr"][xix] += v
	Graph["Iarr"][xix] += i
	Graph["n"] += 1
	n = Graph["n"]
	if n == Graph["PtPerPix"]: # time to draw new data point		
		Graph["n"] = 0
		v = Graph["Varr"][xix] / n
		Graph["Varr"][xix] = v
		AutoScale("V", v)
		DrawGraphPixel(xix, "V", RED)

		v = Graph["Iarr"][xix] / n
		Graph["Iarr"][xix] = v
		AutoScale("I", v)
		DrawGraphPixel(xix, "I", BLUE)

		Graph["Xix"] += 1  
		if Graph["Xix"] == MAXX: #  re-scale x by half
			wix = 0
			for xix in range(0, MAXX, 2):
				Graph["Varr"][wix] = (Graph["Varr"][xix] + Graph["Varr"][xix+1]) / 2.0
				Graph["Iarr"][wix] = (Graph["Iarr"][xix] + Graph["Iarr"][xix+1]) / 2.0
				wix += 1
			InitGraph(MAXX // 2)
			Graph["PtPerPix"] += Graph["PtPerPix"] # exponential re-scaling			
			RedrawGraph()

		# prepare next pixel summing
		xix = Graph["Xix"]
		Graph["Varr"][xix] = 0   
		Graph["Iarr"][xix] = 0

def ProcessMessages():
	msg=usb.Scan().lower()
	if not msg: return msg
	try: 
		if (msg[0:10]=='set_range='):
			r = int(msg[10:])
			if (0<=r<=5):
				cfg["Range"] = r 
				DisplayCfg()
				ads.setVoltageRange_mV(ADS1115_RNG[r])
				print('Range set to ix',r)
		elif msg[0:9]=='set_mode=':
			r = int(msg[9:]) 				
			cfg["Mode"] = r
			DisplayCfg()
			print('Mode set to ix', r)
		elif msg[0:9]=='set_cal=(':
			r = msg[9:-1].split(',') 			
			fr = [float(item) for item in r]
			cfg["R"] = fr 
			DisplayCfg()
			print('Cal set to: ',fr)
		elif msg[0:12]=='set_scales=(':
			r = msg[12:-1].split(',') 			
			fr = [float(item) for item in r]
			cfg["VScale"] = fr[0:2]
			cfg["IScale"] = fr[2:]
			DisplayCfg()
			print('scales set: ', r)
			RedrawGraph()
		elif msg=='save_cfg': 				
			print('saved config')
			SaveCfg()
		elif msg=='restart':
			Restart(True)
		elif msg[0:12]=='set_totals=(':
			r = msg[12:-1].split(',')
			fr = [float(item) for item in r]
			state["Ah"] = fr[0]
			state["Wh"] = fr[1]
			DisplayTop()
		elif msg[0:8]=='upload=(': # receive 
			if not display["Pause"]:
				ShowPause()
				InitGraph()
			r = msg[8:-1].split(',')
			fr = [float(item) for item in r]
			for ix in range(0,len(fr), 2): 
				GraphAddPt(fr[ix], fr[ix+1])
			RedrawGraph()
			# handshake for graph part
			print(">>ok<<") 
		elif msg[0:8]=='unpause(':  # value is PtPerPix
			Graph["PtPerPix"] = int(msg[8:-1])
			if display["Pause"]:
				display["Pause"] = 0
				display["Error"] = 0
				RedrawGraph()
		elif msg[0:9]=='get_file(':
			fn = msg[9:-1]
			SendFile(fn)
	except:
		ShowError(['Parse Err:','msg=',msg[0:12]])
	return msg

def SendFile(fn):
	try:
		print("\1",end="")
		#print('Bob')
		with open(fn, 'r') as file:
			for line in file: print(line, end='')
		print() # force at least 1 linefeed
	except:		
		pass
	print('\1') # on error: empty file returned
	if fn=="state.json": RestoreState()

def ShowPause(Msg = 'Pause', color=GREY):
	display["Pause"] = 1
	ShowError(Msg, color=color)

# Splash = short message to give action feedback
def ShowSplash(Msg, color=DGREEN, time_ms = 1500):
	display["Splash"] = time.ticks_ms() + time_ms
	ShowMsg(Msg, color)

def ShowError(ErrMsg = 'Error', color=RED):
	display["Error"] = 1
	if isinstance(ErrMsg, str): ErrMsg = [ErrMsg]
	display["ErrMsg"] = ErrMsg
	ShowMsg(ErrMsg, color)

def ShowMsg(Msg, color):
	if isinstance(Msg, str): Msg = [Msg]
	w = 0
	for s in Msg: w = max(w,tft.draw_len(font, s))
	h = round(font.HEIGHT * 1.2)
	y = 10 + (tft.height() - h * len(Msg)) // 2
	x = (MAXX - w) // 2 
	tft.fill_rect(x - 5, y - 2 , w + 10, h * len(Msg) + 4, color)
	y += 12
	for s in Msg:
		tft.draw(font, s, x, y, st7789.WHITE)
		y += h

def SaveCfg():
	try:
		with open("config.json", "w") as f:
			json.dump(cfg, f)
	except:
		ShowError(['Error while','writing:','"config.json"'])

def LoadCfg():
	global cfg
	try:
		with open("config.json", "r") as f:
			cfg = json.load(f)
	except:
		pass  # if no config file, use defaults

# Temperature cleanup code for pico noisy adc
# tol: tolerance relative to average that will be exluded when n >= 10
@micropython.native
def ReadTemp(n=200, tol = 0.05): 
	tot = 0
	for i in range(n):
		t = 3.3 * adc.read_u16()/65536
		t = (t / 0.005) - 273.15
		tot += t

	avg = tot / n
	# Redo but this time exclude outliers (far from avg)
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

def Display(x, y, text, fg = st7789.WHITE, bg = st7789.BLACK,  sc = 1.3):	
	if not isinstance(text, str): text = str(text)	
	w =  tft.draw_len(font, text, sc)
	if x < 0: x = MAXX - w + x
	h = round(font.HEIGHT * sc)
	tft.draw(font, text, x, y, fg, sc )

@micropython.native
def DisplayTop():
	global FanMsgCnt
	if display["Error"] and not display["Pause"]: return
	if display["Splash"] and time.ticks_diff(time.ticks_ms(), display["Splash"]) > 0:
		display["Splash"] = 0
		RedrawGraph()

	h = int(round(font.HEIGHT * 1.3))
	y = 2

	tft.fill_rect(MAXX//2+33, y+6, MAXX//2-33, h-4, st7789.BLACK)
	#tft.rect(MAXX//2+33, y+6, MAXX//2-33, h-4, st7789.WHITE)
	Display(-13, y+20, f'{state["V"]:.3f}V', fg=RED)

	tft.fill_rect(0, y+6, MAXX//2-40, h-4, st7789.BLACK)
	#tft.rect(0, y+6, MAXX//2-40, h-4, st7789.WHITE)
	Display(5, y+20, f'{state["A"]:.2f}A', fg=BLUE)

	y = 30
	tft.fill_rect(MAXX//2+35, y+6, MAXX//2-35, h-4, st7789.BLACK)
	#tft.rect(MAXX//2+35, y+6, MAXX//2-35, h-4, st7789.WHITE)
	v = state["Wh"]
	fv =f'{v:.2f}Wh' if v<10 else f'{v:.1f}Wh'
	Display(-1, y+20, fv, fg=ORANGE)

	v = state["Ah"]
	fv =f'{v:.2f}Ah' if v<10 else f'{v:.1f}Ah'
	tft.fill_rect(0, y+6, MAXX//2-40, h-4, st7789.BLACK)
	#tft.rect(0, y+6, MAXX//2-40, h-4, st7789.WHITE)
	Display(5, y+20, fv, fg=GREEN)

	y = 16
	v = state["T"]
	fv =f'{v:.1f} '
	if v<0: 
		fv = '--'
		if FanMsgCnt < 5:
			ShowSplash(["Turn on Fan!","(POWER button)"],color=st7789.MAGENTA)
			FanMsgCnt += 1
	else: FanMsgCnt = 0

	w =  tft.draw_len(font, fv, 1.2)
	x0 = (MAXX-w)//2
	tft.fill_rect(MAXX//2-36, y+2, 68, 28, st7789.BLACK)
	# tft.rect(MAXX//2-36, y+2, 68, 28, st7789.WHITE)
	Display(x0, y+20, fv, fg=st7789.YELLOW, sc = 1.2)
	tft.circle(x0+w-11, y+6, 3, st7789.YELLOW)

def DisplayCfg():
	if display["Error"]: return
	tft.fill_rect(0, 210, MAXX, font.HEIGHT, st7789.BLACK)
	Display(1, 220, f'Mode:{MName[cfg["Mode"]]}', fg=GREY, sc=1)
	Display(-1, 220, f'Range:{RNGV[cfg['Range']]}', fg=GREY, sc=1)

def Restart(rst = False):
	if rst:
		state["Ah"] = 0
		state["Wh"] = 0
	display["Pause"] = 0
	display["Error"] = 0
	InitGraph()
	RedrawGraph()	

def Disconnect():
	# do not disconnect near a relay state change
	if display["RelayDelay"]>0: 
		if time.ticks_diff(display["RelayDelay"], time.ticks_ms())<0:
			return
		else:
			display["RelayDelay"] = 0
	if cfg["SMode"] < 2: return

	lim = SLIMITS[cfg["SMode"]]
	if (state["A"] > lim[0]) and not (lim[1] <= state["V"] <= lim[2]):		
		SaveState()
		relay.value(0)
		ShowError("Auto Cut Out")

@micropython.native
def Cumulate(vals, dt):
	vrix = 1 if cfg["Mode"] == 2 else 0  # R1 or RP: ix = 0, RS: ix = 1
	v = vals[2]
	r = cfg["R"][cfg["Mode"]]
	vr = vals[vrix] 

	# take relay state into account to compute i
	# voltage across resistor is not valid when relay is off
	i = max(0, vr / r) if relay.value() else 0
		
	dt /= SPH  #  dt in hours
	state["A"] = i
	state["V"] = v
	state["Ah"] += i * dt
	state["Wh"] += max(0,v * i * dt)
	GraphAddPt(v, i)

def ToggleRelay():
	relay.value(1 - relay.value()) 
	display["RelayDelay"] = time.ticks_ms() + 3000 
	msg = "On" if relay.value() else "Off"
	ShowSplash(f'Relay: {msg}')

def ExecBtnPress():
	#tft.fill_rect(100, 100, 200, 30, st7789.BLACK)
	#Display(100,120,f'{Keys:04b}')
	BLUE_BTN   = 1
	RED_BTN    = 2
	GREEN_BTN  = 4
	YELLOW_BTN = 8

	Keys = KeyTrack["Last"]
	long = KeyTrack["n"] >= 200 # 200 * 10ms = 2 sec => long press

	if Keys == GREEN_BTN:
		if long:
			cfg["SMode"] += 1
			if cfg["SMode"] >= len(SMODES): cfg["SMode"] =0
			ShowSplash(["SMode set to:", SMODES[cfg["SMode"]], str(SLIMITS[cfg["SMode"]][1:])])
			KeyTrack["Long"] = True
			SaveCfg()
		else:
			ToggleRelay()

	elif Keys == RED_BTN or Keys == YELLOW_BTN:
		d = 1 if Keys == RED_BTN else -1
		old = cfg["Range"]
		cfg["Range"] += d
		if cfg["Range"]>5: cfg["Range"] = 5 
		if cfg["Range"]<0: cfg["Range"] = 0
		if old != cfg["Range"] : print(f'>Range:{cfg["Range"]}')
		DisplayCfg()
		ads.setVoltageRange_mV(ADS1115_RNG[cfg["Range"]])
		SaveCfg()

	elif Keys == BLUE_BTN: 
		old = cfg["Mode"] 
		cfg["Mode"] += 1
		if cfg["Mode"]>2: cfg["Mode"] = 0 
		if cfg["Mode"]<0: cfg["Mode"] = 2
		if old != cfg["Mode"] : print(f'>Mode:{cfg["Mode"]}')
		DisplayCfg()
		SaveCfg()
	elif Keys == BLUE_BTN + GREEN_BTN: # 5 blue and green
		Restart(long)
		KeyTrack["Long"] = long
	elif Keys == RED_BTN + YELLOW_BTN: # 10 red + yellow	(toggle-autoscale)
		cfg["AutoScale"] = 1 - cfg["AutoScale"]
		if (Graph["Xix"] > 0) and cfg["AutoScale"]: 
			ReScale()
		else:
			RedrawGraph()
	elif Keys == BLUE_BTN + RED_BTN:
		SaveState()
	elif Keys == BLUE_BTN + YELLOW_BTN:
		RestoreState()

	KeyTrack["n"] = 0
	KeyTrack["Last"] = 0

@micropython.native 
def ReScale():
	for g in ["V","I"]:
		max = -9999; min = 9999
		data = Graph[g + "arr"]
		for ix in range(0, Graph["Xix"] - 1):
			if data[ix] > max: max = data[ix]
			if data[ix] < min: min = data[ix]
		mid = (max + min) / 2
		ds = (max - min) * 1.2
		cfg[g + "Scale"][0] = mid - ds
		cfg[g + "Scale"][1] = mid + ds
		RedrawGraph()

def SaveState():
	try:
		with open("state.json", "w") as f:
			json.dump({"Graph":Graph, "state":state}, f)
		ShowSplash("State Saved")
	except:
		ShowError(['Error while','writing:','"state.json"'])	

def RestoreState():
	global Graph, state
	try:
	#if 1==1:
		with open("state.json", "r") as f:
			s = f.read()		
		s = s.replace("array('f', [","[")
		s = s.replace("])","]")
		# print(s)

		js = json.loads(s)
		#print(js)
		Graph = js["Graph"]
		Graph["Varr"] = array.array('f',Graph["Varr"])
		Graph["Iarr"] = array.array('f',Graph["Iarr"])
		gc.collect()
		state = js["state"]
		ReScale()
		ShowPause()
	except:
		Restart(True) # no saved file, clear graph

@micropython.native
def CheckKeys():	
	Keys = btns.key1.value() + (btns.key2.value() << 1) + (btns.key3.value() << 2) + (btns.key4.value() << 3)
	Keys ^= 0xF

	err = display["Error"]  # 0 no errr, 1: wait any button pressed, 2: wait release
	if err:
		if Keys == 0:
			if err == 2: # any button was pressed and released. hide error
				display["Error"] = 0  
				display["Pause"] = 0
				tft.fill(st7789.BLACK)
				DisplayTop()
				DisplayCfg()
				RedrawGraph()
			return  # wait for keypressed
		if Keys > 0 and err == 1: display["Error"] = 2 # request wait for release
		return

	if KeyTrack["Long"]:
		if Keys == 0: KeyTrack["Long"] = False
		return

	# actions are on release to allow multi button press
	if Keys == 0:
		if (KeyTrack["n"]>10):  # do action
			ExecBtnPress() 		
	elif Keys>KeyTrack["Last"]:
		KeyTrack["Last"] = Keys
		KeyTrack["n"] = 0
	elif Keys > 0 and Keys == KeyTrack["Last"]:
		KeyTrack["n"] += 1
		if KeyTrack["n"] >= 200: # long press
			ExecBtnPress()

import math 

@micropython.native # comment when debugging to get error line numbers
def main():
	tft.init()
	tft.fill(st7789.BLACK)

	ShowError(f"Version: {VERSION}",  st7789.color565(32,32,32))
	time.sleep(2)
	display["Error"] = 0

	LoadCfg()
	DisplayCfg()
	RedrawGraph()

	Avg_Cnt = 64
	delay = 2_000_000 # 2_000_000 # us
	delay_s = delay // 1_000_000 

	ads.setAvgCNt(Avg_Cnt)
	ads.setVoltageRange_mV(ADS1115_RNG[cfg["Range"]])
	ads.setConvRate(ADS1115_250_SPS)

	Chnls = (0, 1, 7) # AIN0, AIN1, AIN0-AIN1 (R1, R1+R2, V)
	t0 = time.ticks_us()

	lcnt = 0
	while(True):
		# periodical stuff (every minute)
		lcnt += 1
		if lcnt * delay_s >= 60: 
			lcnt = 0; 
			ads.setVoltageRange_mV(ADS1115_RNG[cfg["Range"]]) # re-set gain amp  

		DisplayTop()
		while time.ticks_diff(time.ticks_us(), t0) < delay:
			ProcessMessages()
			CheckKeys()
			time.sleep_ms(10)
			# v = 3.3+0.3*math.sin(x); i = 7+4*math.cos(0.5*x); GraphAddPt(v, i);	x += 0.1 # debug graph function
		t1 = time.ticks_us()
		dt = time.ticks_diff(t1, t0) / 1000000
		t0 = t1

		rt = round(ReadTemp(),1) # resistance temperature
		vals = ads.readMulti(Chnls) 
		if not display["Pause"]: 
			print("acq=", end="")
			print(vals + (rt,))
			Cumulate(vals, dt)
			Disconnect()
		state["T"] = rt				
main()
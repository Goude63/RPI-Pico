
import rp2, gc, time, network, socket, ubinascii, urequests, sys, math, utime
from machine import Pin
import st7789, tft_config, micropython, json, io
import romancs as font
from lifepower import LifePower

PAGES = [
	["Vue d'ensemble:",('PV(W)','PV','W',st7789.YELLOW),('AC_out(W)','Inv','W',st7789.MAGENTA), 
  		('Batt(W)','Bat','W',st7789.BLUE), ('BattSOC','Bat','%',st7789.GREEN), ('pwr','HQ','kW',st7789.RED)],
	["Batteries:", ('BattSOC','SOC','%',st7789.GREEN),('Batt(W)','BatW','W',st7789.BLUE), 
  		('Batt(A)','BatA','A',st7789.CYAN), ('Batt(V)','BatV','V',st7789.MAGENTA) ],
	["Inverter:", ('PV(W)','PV','W',st7789.YELLOW),('AC_out(W)','Pwr','W',st7789.RED),
  		('AC_out(V)','V Out','V',st7789.MAGENTA), ('AC_out(A)','A Out','A',st7789.BLUE), 
		('Load','Load','%',st7789.CYAN)]
]

def Connect():
    global sock, wlan
    wlan.active(True) 
    wlan.connect('sous-sol', 'bonjourlapolice')           

    n = 0
    while wlan.status() > 0 and wlan.status() < 3 and n < 30:
        time.sleep(1)
        n += 1
        print('*', end = '')
    
    if wlan.status() == 3:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP 
        mac = ubinascii.hexlify(network.WLAN().config('mac'),':').decode()
        print('Mac=', mac)
    else:
        print(wlan.status())

def DoLog(msg, end='\r\n'):
    global sock
    msg = msg + end
    try:
        sock.sendto(msg.encode('ascii'), ("192.168.1.101", 4321))
    except: pass

def get_val(name,unit): # unit used to properly round e.g. kW keep 3 digits
	s = all.find(name + ' = ')
	if s < 0: return '---'
	s += len(name) + 3
	er = all.find('\r',s)
	en = all.find('\n',s)
	if en < er: er = en
	v = all[s:er]
	try:
		v = float(v)
		if unit.lower() == 'kw':
			v = round(v*1000)
			unit = 'W'
		elif unit == '%':
			v = round(v)
		else:
			v = round(v,1)
		if round(v) == v: v = int(v)
	except:
		pass
	return (str(v), unit)

def display():
	global all, page, tft
	scale = 1.1
	x,y = (5,33)
	if len(PAGES[page])<6: y += 10
	tft.fill(st7789.BLACK)
	for item in PAGES[page]:
		if type(item) == type(''):	 
			tx = 120 - tft.draw_len(font, item, scale) // 2
			tft.draw(font, item, tx, 7, st7789.WHITE, scale)
		else:
			s = item[1] + ' :'
			tx = 100 - tft.draw_len(font, s, scale)
			tft.draw(font, s, tx, y, item[3], scale)
			v,u = get_val(item[0],item[2])
			tft.draw(font, v + ' ' + u, 110, y, item[3], scale)
			y += 21

class Buttons():
    def __init__(self):
        self.up    = Pin(2,Pin.IN,Pin.PULL_UP)
        self.down  = Pin(18 ,Pin.IN,Pin.PULL_UP)
        self.left  = Pin(16,Pin.IN,Pin.PULL_UP)
        self.right = Pin(20,Pin.IN,Pin.PULL_UP)
        self.sel   = Pin(3,Pin.IN,Pin.PULL_UP)
        self.KeyA  = Pin(15,Pin.IN,Pin.PULL_UP)
        self.KeyB  = Pin(17,Pin.IN,Pin.PULL_UP)

def hand_polygon(length, radius):
    return [
        (0, 0),
        (-radius, radius),
        (-radius, int(length * 0.3)),
        (-1, length),
        (1, length),
        (radius, int(length * 0.3)),
        (radius, radius),
        (0,0)
    ]

def watch(lp, ac):
	global tft
	'''
	Draw analog watch face and update time
	'''
	# enable display
	btns = Buttons()
	width = tft.width()
	height = tft.height()
	radius = min(width, height)         # face is the smaller of the two
	ofs = (width - radius) // 2         # offset from the left to center the face
	center_x = radius // 2 + ofs - 1    # center of the face horizontally
	center_y = radius // 2 - 1          # center of the face vertically

	# draw the watch face background
	face = "face_{}x{}.jpg".format(width, height)
	tft.jpg(face, 0, 0, st7789.SLOW)

	# create the polygons for the hour, minute and second hands
	# polygons must be closed convex polygons or bad things(tm) happen.

	second_len = int(radius * 0.65 / 2)
	second_poly = hand_polygon(second_len, 2)

	minute_len = int(radius * 0.6 / 2)
	minute_poly = hand_polygon(minute_len, 2)

	hour_len = int(radius * 0.5 / 2)
	hour_poly = hand_polygon(hour_len, 3)

	# constants for calculating hand angles.
	pi_div_6 = math.pi/6
	pi_div_30 = math.pi/30
	pi_div_360 = math.pi/360
	pi_div_1800 = math.pi/1800
	pi_div_2160 = math.pi/2160

	# initialize variables for the bounding rectangles for the
	# hour, minute and second hands. Calling bounding with True will
	# reset the bounds, calling with False will disable bounding

	tft.bounding(True)
	hour_bound = tft.bounding(True)
	minute_bound = tft.bounding(True)
	second_bound = tft.bounding(True)

	n = 0

	while n <= 10:
		n += 1
		# save the current time in seconds so we can determine when
		# when to update the display.
		last = utime.time()

		# get the current hour, minute and second
		_, _, _, hour, minute, second, _, _ = utime.localtime()

		# constrain hours to 12 hour time
		hour %= 12

		# calculate the angle of the hour hand in radians
		hour_ang = (
			(hour * pi_div_6) +
			(minute * pi_div_360) +
			(second * pi_div_2160) +
			math.pi)

		# calculate the angle of the minute hand in radians
		minute_ang = ((minute*pi_div_30)+(second*pi_div_1800)+math.pi)

		# calculate the angle of the second hand on radians
		second_ang = (second*pi_div_30+math.pi)

		# erase the bounding area of the last drawn hour hand
		x1, y1, x2, y2 = hour_bound
		tft.fill_rect(x1, y1, x2, y2, st7789.WHITE)

		# erase the bounding area of the last drawn minute hand
		x1, y1, x2, y2 = minute_bound
		tft.fill_rect(x1, y1, x2, y2, st7789.WHITE)

		# erase the bounding area of the last drawn second hand
		x1, y1, x2, y2 = second_bound
		tft.fill_rect(x1, y1, x2, y2, st7789.WHITE)

		# draw the hub after erasing the bounding areas to reduce flickering
		tft.fill_circle(center_x, center_y, 5, st7789.BLACK)

		tft.bounding(True)      # clear bounding rectangle

		# draw and fill the hour hand polygon rotated to hour_ang
		tft.fill_polygon(hour_poly, center_x, center_y, st7789.BLACK, hour_ang)

		# get the bounding rectangle of the hour_polygon as drawn and
		# reset the bounding box for the next polygon
		hour_bound = tft.bounding(True, True)

		# draw and fill the minute hand polygon rotated to minute_ang
		tft.fill_polygon(minute_poly, center_x, center_y, st7789.BLACK, minute_ang)

		# get the bounding rectangle of the minute_polygon as drawn and
		# reset the bounding box for the next polygon
		minute_bound = tft.bounding(True, True)

		# draw and fill the second hand polygon rotated to second_ang

		tft.fill_polygon(second_poly, center_x, center_y, st7789.RED, second_ang)

		# get the bounding rectangle of the second_polygon as drawn and
		# reset the bounding box for the next polygon
		second_bound = tft.bounding(True, True)

		# draw the hub again to cover up the second hand
		tft.fill_circle(center_x, center_y, 5, st7789.BLACK)

		# wait until the current second changes
		while last == utime.time():
			if (btns.up.value() and btns.KeyA.value() and btns.down.value() and 
				btns.sel.value() and btns.KeyB.value()):
				MySleep(50, lp, ac)
			else:
				n = 1000

#Check for power failure and water heater 110V/220V/0V
@micropython.native
def chk_ac(p, n=32, v0=220):
    x = 0
    for i in range(0,n): 
        if (p.value()): x += 1
        time.sleep_us(500)   
    # print(x*100/n, end='-')
    if x == 0: return v0
    elif x == n: return 0
    else: return 110

def SendPack(lp):
	s = EncodeURI(json.dumps(lp.Pack))
#	r = urequests.get('http://192.168.1.189/rest/Eg4Ctrl/Updt/Pack?' + s)
	r = urequests.get('http://192.168.1.202/rest/Eg4Ctrl/Updt/Pack?' + s)
	d=r.content.decode('ascii')
	r.close

def SendAC(ac):
	s = EncodeURI(json.dumps({"AC_ChEau": ac['ch_eau'], "AC_Hydro": ac['hydro']}))
#	r = urequests.get('http://192.168.1.189/rest/Eg4Ctrl/Updt/AC?' + s)
	r = urequests.get('http://192.168.1.202/rest/Eg4Ctrl/Updt/AC?' + s)
	d=r.content.decode('ascii')
	r.close

# sleep that checks for new lifepower messages
@micropython.native
def MySleep(ms, lp, ac):  # returns true if new message from lifepower
	start = time.ticks_ms()
	while time.ticks_diff(time.ticks_ms(), start) <= ms:
		if lp.ProcessMsg():	SendPack(lp)
		else: 
			x = chk_ac(ac['pin_che'])
			chng =  (x != ac['ch_eau'])
			ac['ch_eau'] = x
			x = 0 if ac['pin_eg4'].value() else 110
			chng |= (ac['hydro'] != x)
			ac['hydro'] = x
			if chng: SendAC(ac)
			time.sleep_us(500)

# limited to space and quotes encoding (to pass JSON data)
@micropython.native
def EncodeURI(s):
	#calculate required buffer size = len s - spaces count + 2 * quote cnt
	size = len(s)
	for i in range(0,len(s)):
		if s[i] == ' ': size -= 1
		if s[i] == '"': size += 2

	fs = io.StringIO(size)

	for i in range(0,len(s)):
		if s[i] != ' ':
			if s[i] == '"': fs.write('%22')
			else: fs.write(s[i])

	fs.seek(0)
	return fs.read()

#
#  Main code
#
def main():
#if True: # when debugging, have easy access to all variables => not in a function = all globals
	# machine.freq(200000000)

	global font, all, page, tft, wlan

	# ac detection info "object"
	pin_che = Pin(6, Pin.IN)
	pin_eg4 = Pin(7, Pin.IN)
	ac = { "pin_eg4" : pin_eg4,	"pin_che" : pin_che, "ch_eau" : -1, "hydro" : -1 }

	lp = LifePower()

	tft = tft_config.config(1, buffer_size=16*32*2)
	tft.init()
	tft.fill(st7789.BLACK)
	btns = Buttons()

	rp2.country('CA')
	wlan = network.WLAN(network.STA_IF)
	network.hostname("LCD_pico")
	Connect()

	ip4 = ['189', '200']  # ['100'] for debug on pc
	excpt_cnt = 0
	run = True
	rtc_set = False
	page = 0

	while run:
		try:
		#if 1==1:
			if  wlan.status() != 3:
				wlan.disconnect()
				Connect()
			if wlan.status() == 3:
				gc.collect()
				try:
					for ad4 in ip4:
						addr = "http://192.168.1." + ad4 + ":8889/"

						if not rtc_set:
							r = urequests.get(addr + 'date')
							d=r.content.decode('ascii')
							print(d)
							r.close
							rtc = machine.RTC()
    						#  YYYY,MM,DD,wd,HH,MM,SS,0   
							rtc.datetime((int(d[0:4]), int(d[5:7]), int(d[8:10]), -1, 
								int(d[11:13]), int(d[14:16]), int(d[17:19]), 0))
							rtc_set = True

						r = urequests.get(addr + 'all')
						all = r.content.decode('ascii')
						r.close()
						if len(all) > 0 and all[0] == '@':
							display()
							break
				except Exception as error: 
					print('Exception:', error)
			i = 1
			while (i < 100) and run: # 10 seconds
				i += 1
				if btns.sel.value() == 0: run = False
				pg_up = not(btns.up.value() and btns.KeyA.value())
				pg_dwn = not(btns.down.value() and btns.KeyB.value())
				if pg_up and pg_dwn: run=False				
				elif pg_up or pg_dwn:
					i = 0
					if pg_up:  page -= 1
					if pg_dwn: page += 1
					if page >= len(PAGES): page = 0
					elif page < 0: page = len(PAGES) - 1
					display()
					MySleep(400,lp,ac)
				MySleep(100,lp,ac)
			if (i>=100) and run: 
				watch(lp, ac)

		except:
		#else:
			excpt_cnt += 1
			DoLog('Exceptions count=' + str(excpt_cnt))
			if excpt_cnt >= 10: machine.reset()
			time.sleep(1)
	tft.fill(st7789.BLACK)

main()
machine.freq(250_000_000)
from ST7735 import TFT
from CLT1100 import CLT1100
from f_sys	 import f_sys
from f_10x14 import f_10x14
from machine import SPI,Pin
import time, math

#########################################
#		Global module "Constants"		#
#########################################
# ttf setup
FW = (f_sys["Width"] + 1, f_10x14["Width"] + 1) # the tft.text function adds 1 pixel between 5 pic characters 
FH = (f_sys["Height"] + 1, f_10x14["Height"] + 2)
FONTS = (f_sys, f_10x14)  # second font must be double size of font1
PIXWIDTH	= 160
PIXHEIGHT	= 128
CARWIDTH	= PIXWIDTH // FW[0]
CARHEIGHT	= PIXHEIGHT // FH[0]
ROTATION	= 1
LONG_BTN_MS	= 500

# information for editing items. 
# type: b = boolean, w = wave shape, i,f = integer float
#    u: unit, defd = default digit/multiplicator, defv = def value
# Note: defd is the equivalent power of 10 for unit digit, -1 for first decimal digit
# shape: 0: sine, 1: square, 2: triangular, 3: sawtooth hard ledt, 4: sawtooth hard right, >=5 arbitrary
# for arbitrary, a file name arb_n.u16 must exist on local file system
EDIT_DEF =  {  # defaults: defv:0, defd:0, res:min (1 for type i), color: green
'Ch': {
	'0': {'name':'on', 'type':'b','min':0,   'max':1,  'u':'',  'res' :1},
	'1': {'name':'sh', 'type':'w','min':0,   'max':8,  'u':'',  'res' :1}, # TBD calculate max from files
	'2': {'name':'Fr', 'type':'f','min':0.1, 'max':5e6,'u':'Hz','defd':2, 'color':TFT.BLUE,'defv':1000},
	'3': {'name':'Am', 'type':'f','min':1e-3,'max':10, 'u':'V', 'defv':1, 'color':TFT.PURPLE},
	'4': {'name':'Of', 'type':'f','min':-10, 'max':10, 'u':'V', 'defd':-3,'res'  :1e-3, 'color':TFT.ORANGE},
	'5': {'name':'Ph', 'type':'i','min':-181,'max':180,'u':'o', 'defd':1, 'color':TFT.GRAY},
	'6': {'name':'Dt','type':'f','min':0,'max':100,'u':'%','defv':50,'defd':1,'res':0.1,'color':TFT.CYAN}},
'Cfg': {
	'0':{'name':'Brightness', 'type':'i','min':10,'max':100, 'u':'%', 'defd':1, 'defv':80,'res':10},
	'1':{'name':'Volt Limit', 'type':'f','min':1, 'max':10,  'u':'V', 'defv':3, 'res':0.1}}}	

# Editable elements values, factor/digit, col, row, font size of current screen location
EDIT_VALS = {}
PAGES = { 
	'Top':{'layout':'2x2', 'blocks':['Ch'] * 4 },
	'Cfg':{'layout':'1', 'blocks':['Cfg']}}

# FOCUS / DIGIT info
FOCUS  = {'block':0, 'pix': 2}  #'param':'fr', 
ACTIVE = ''
PAGE   = {}
ZOOM = False

# returns (param name, string value including units, color
# cofs = horizontal 1st character display offset, ei = index in string where focus is) 
@micropython.native
def gformat(bix, pix, g):
	spix = str(pix)
	pix=int(pix); bix = int(bix)
	p = EDIT_DEF[g][spix]['name']
	v = g + '_' + str(bix)               # variable / value e.g. Ch_1
	color = EDIT_DEF[g][spix]['color']
	
	# initial ei value relative to decimal point (changed later to offset in string)
	ei = -int(FOCUS[p])-1 if FOCUS['block'] == bix and FOCUS['pix'] == pix else None
	# print(p, FOCUS['block'], bix, FOCUS['pix'], pix, ei, FOCUS['block'] == bix, FOCUS['pix'] == pix, type(bix), type(pix) )

	raw =EDIT_VALS[v][p] # ['value']
	s=''; sh = 0
	db = EDIT_DEF[g][spix] 
	u = db['u']
	
	p = p+':'
	if u == 'Hz':
		p =''
		if raw>=1e6   	: s = f'{raw/1e6:7.3f}'; u='MHz'; sh = 6
		elif raw>1000 	: s = f'{raw/1e3:7.3f}'; u='KHz'; sh = 3
		else			: s = f'{raw:7.1f}';     u=' Hz'; sh = 0
	elif u == 'V':
		if abs(raw)>0.5 or abs(raw) <1e-5:	s = f'{raw:6.3f}'; sh = 0
		else:	s = f'{raw*1000:4.0f}'; u=' mV'; sh = -3 
	elif u == 'o':
		s = f'{raw:3.0f}'; sh = 0
	elif u=='%':
		sh = 0
		if db['res'] == 1: s = f'{raw:3.0f}'
		else: s = f'{raw:5.1f}'
	
	# adjust edit character index from left of string
	# ei is 'edit index': index of digit == adjust factor in 's' string
	if ei is None: 
		ei = -1 # not focused param
	elif p in ['sh:', 'on:']:
		ei=1
	else:
		dp = s.find('.')
		add_dp = dp<0
		if add_dp: 
			dp = len(s); 
			s += '.' # add temp '.' as reference
		ei = ei + dp + sh
		if ei>=dp: ei += 1
		if add_dp: s = s[:-1] # remove temp '.'

	return (p, f'{s} {u}', color, ei)

# wrapper that uses character sizes as coordinates 
def text(col,row, txt, fix, color=TFT.WHITE, xof=0, yof=0):
	if fix > 1: fix = 1
	fw = FW[fix]; fh = FH[fix]
	tft.text((xof+col*fw, yof+row*fh), txt, color, FONTS[fix])

#TFT(spi, aDC, aReset, aCS, aLED)
class SGUI:
		# 'defv' not stated: =0. 'res' not stated: =min. defd not stated: =1
		# parameters start with a 'n-' to facilitate friendly sorted enumeration 

	def __init__(self): 
		global tft
		spi = SPI(0, baudrate=machine.freq()//2, polarity=0, phase=0, sck=Pin(2), mosi=Pin(3), miso=None)
		tft = TFT(spi,4,5,6,46) # REG, RST, /CS, LED
		tft.initr()
		tft.rotation(ROTATION);	tft.rgb(True); tft.fill(); tft.led(75)

		# 2 encoders ( see schematics for pins )
		self.enc = (CLT1100(10, 32, 40), CLT1100(11, 34, 41)) 
		self.btns = 0
		self.btn_wait0 = False
		self.E2Mode = 'Param'  # vs 'Digit'

		self.savebix = FOCUS['block']
		self.savepix = FOCUS['pix']

		# add default params keys' EDIT_VALS (defv, res and defd)
		for grp in EDIT_DEF: 				# grp = 'Ch', 'cfg'...
			for pix in EDIT_DEF[grp]:		# pix = '1', '2' ...
				if not 'defv' in EDIT_DEF[grp][pix] : EDIT_DEF[grp][pix]['defv'] = 0
				if not 'color' in EDIT_DEF[grp][pix]: EDIT_DEF[grp][pix]['color'] = TFT.GREEN

				if not 'res' in EDIT_DEF[grp][pix]: 
					t = EDIT_DEF[grp][pix]['type']
					EDIT_DEF[grp][pix]['res'] = 1 if t=='i' else EDIT_DEF[grp][pix]['min'] 

				# set focus digit for all parameter types
				if 'defd' in EDIT_DEF[grp][pix]: 
					FOCUS[EDIT_DEF[grp][pix]['name']] = EDIT_DEF[grp][pix]['defd']
				else:
					FOCUS[EDIT_DEF[grp][pix]['name']] = 0

		# create current EDIT_VALS for all parameters, and default focused digit/factor
		for grp in EDIT_DEF:
			if grp in ['Ch']:
				names = []
				for i in range(4): names.append(grp + '_' + str(i))
			else: names=[grp + '_0']

			for name in names:
				EDIT_VALS[name] = {}
				for pix in EDIT_DEF[grp]:
					pn = EDIT_DEF[grp][pix]['name']
					EDIT_VALS[name][pn] = {}
					EDIT_VALS[name][pn] = EDIT_DEF[grp][pix]['defv']
 
	# draw on/off led and shape icon, including grey focus rectangle
	def DrawIcon(self, pn, bix, xof, yof, ei):
		v = EDIT_VALS['Ch_'+ str(bix)][pn]
		fix = 1 if ZOOM else 0
		fw = FW[fix]
		y = yof + fw*1.4
		if pn=='on':
			x = xof + 5*fw
			r = fw*0.8
			d = r * 1.2
			if v: 
				tft.fillcircle((x, y), r, tft.GREEN)
			else:
				tft.fillcircle((x, y), r, tft.BLACK)
				tft.circle((x, y), r, tft.WHITE)
			if ei >= 0:
				d = r * 1.3
				tft.rect((x-d, y-d),(2.3*d, 2.1*d), tft.GRAY)
		else: # 'sh'
			x = xof + 7*fw
			w = fw*5+4
			c = tft.BLACK
			tft.fillrect((x, y-fw),(fw*5,fw*2+1), tft.WHITE)
			if ei>=0: tft.rect((x-2, y-fw-2),(w,fw*2+5), tft.GRAY)

			if v >= 5:
				tft.set_BG_Color(tft.WHITE)
				text(7.5,0.6,f'Arb{v-4}', fix, c, xof, yof)
				tft.set_BG_Color(tft.BLACK)
				return

			w -= 2
			x+=1; xn = x + w
			while x <= xn:
				x += 1


	@micropython.native
	def DrawParam(self, bix, pix, g):
		pn = EDIT_DEF[g][str(pix)]['name']

		# skip dusy cycle for non square wave shape		
		if pn=='Dt' and EDIT_VALS['Ch_'+ str(bix)]['sh']!=1: return
		(h, s, c, ei) = gformat(bix, pix, g)

		color = tft.WHITE
		col=0; row=0
		l2x2 = PAGES[ACTIVE]['layout'] == '2x2'

		xof = 0; yof = 0
		if l2x2:
			if not ZOOM: 
				xof = (bix%2)*(PIXWIDTH//2); yof = (bix//2)*(PIXHEIGHT//2)
			rof = int(pix)
		else:
			rof = 1 + 3*int(pix)

		if ZOOM or not l2x2: 
			w = PIXWIDTH
			fix = 1; fw = FW[1]; fh = FH[1]
		else:
			w = PIXWIDTH//2
			fix = 0; fw = FW[0]; fh = FH[0]

		if pn in ['sh', 'on'] :
			self.DrawIcon(pn, bix, xof, yof, ei)
		else:			
			row += rof
			if l2x2:
				s = f'{h}{s}'; 
				if ei>=0: ei += len(h)
				text(col+1, row, s, fix, c, xof, yof)
			else:
				text(col+1, row, h, fix, tft.WHITE, xof, yof)
				row += 1; col += 2
				text(col+1, row, s, fix, c, xof, yof)

			if ei>=0: 
				c ^= 0xFFFFFF
				x = xof + (col+1+ei) * fw
				y = yof + (row+1)*fh - 1				
				text(col+1+ei, row, s[ei], fix, c, xof, yof)

				if self.E2Mode == 'Param': 
					w -= col*fw   # prevent box overflow to the right
					tft.rect((xof+col*fw + 2, yof+row*fh - 1),(w-6, fh + 1), tft.GRAY) 
				else: 
					tft.line((xof+fw,y),(xof+w-fw, y),tft.BLACK)  # in erase previous digit underscore
					tft.line((x,y),(x+fw,y),tft.RED) # draw underscore	

	@micropython.native
	def DrawBlock(self, bix): 
		gr = PAGES[ACTIVE]['blocks'][bix]

		if ZOOM or gr == 'Cfg':
			tft.fill()
			if gr == 'Ch':
				text(0.6, 0.6, f'{gr}{bix+1}', 1, tft.WHITE)
		else:
			w = PIXWIDTH//2; h=PIXHEIGHT//2
			x = (bix%2) * w; y = (bix//2) * h
			tft.fillrect((x,y), (w, h), tft.BLACK)
			if bix==FOCUS['block'] and gr=='Ch':
				tft.rect((x,y),(w-1,h), tft.GREEN)
			text(0.6, 0.6, f'{gr}{bix+1}',0, tft.WHITE, x, y)

		for pix in sorted(EDIT_DEF[gr]):
			self.DrawParam(bix, pix, gr)

	def ShowPage(self, pg, ForZoom = False):   # e.g. call: ShowPage('Top')
		global ACTIVE, PAGE
		ACTIVE = pg
		PAGE = PAGES[pg]
		if PAGE['layout'] =='2x2':
			if not ForZoom:
				FOCUS['block'] = self.savebix
				FOCUS['pix'] = self.savepix
			if ZOOM: 
				self.DrawBlock(FOCUS['block']) 
			else: 
				for i in range(4): self.DrawBlock(i)
		else: 
			if not ForZoom:
				self.savebix = FOCUS['block']
				self.savepix = FOCUS['pix']
				FOCUS['block'] = 0
				FOCUS['pix'] = 0
			self.DrawBlock(0) # Cfh page has just one block
			
	def ChangeSelPar(self, delta):
		if delta == 0: return
		delta = 1 if delta>0 else -1
		gr = PAGES[ACTIVE]['blocks'][FOCUS['block']]

		# TBD update to support config page too
		newix = FOCUS['pix'] + delta

		# handle case for duty cycle only for square wave shape 
		l = len(EDIT_DEF[gr])
		if gr=='Ch' and EDIT_VALS['Ch_'+ str(FOCUS['block'])]['sh']!=1: l -= 1

		if   newix >= l: newix = 0
		elif newix < 0: newix = l - 1

		# TBD update to support config page too
		FOCUS['pix'] = newix
		self.DrawBlock(FOCUS['block'])

	def ChangeSelDigit(self, delta):
		if delta == 0: return
		delta = 1 if delta>0 else -1		
		gr = PAGES[ACTIVE]['blocks'][FOCUS['block']]

		db = EDIT_DEF[gr][str(FOCUS['pix'])]
		d0 = FOCUS[db['name']] 
		d = d0 + delta

		# limit digit according to parameter max/min values
		res = db['res']
		while 10**d < res and d<9: d += 1 
		while 10**d >= db['max'] and d>-3: d -= 1

		if d != d0:
			FOCUS[db['name']] = d
			self.DrawBlock(FOCUS['block'])

	def NextChannel(self):
		prev = FOCUS['block']
		nxt = (FOCUS['block'] + 1) % 4
		FOCUS['block'] = nxt
		if not ZOOM: self.DrawBlock(prev)
		self.DrawBlock(nxt)

	def ExecKnobPress(self, knob, long = False):
		global ZOOM, ACTIVE
		if long:
			self.btn_wait0 = True
			if knob == 1 and ACTIVE=='Top': # no zoom on cfg page
				ZOOM = not ZOOM
				self.ShowPage(ACTIVE, True)
			elif knob == 2:
				np = {'Top':'Cfg','Cfg':'Top'}[ACTIVE]
				self.ShowPage(np) # toggle
		else:
			if knob == 1:  # top nom / E1 
				if ACTIVE=='Top': self.NextChannel()
			else:
				if self.E2Mode == 'Param':
					# shape and on/off do not need select digit
					gr = PAGES[ACTIVE]['blocks'][FOCUS['block']]
					if gr!='Ch' or int(FOCUS['pix'])>=2: 
						self.E2Mode = 'Digit'
						self.DrawBlock(FOCUS['block'])
				else:  # 'Digit'
					self.E2Mode = 'Param'
					self.DrawBlock(FOCUS['block'])

	@micropython.native
	def ChangeValue(self, e):
		bix = int(FOCUS['block'])
		gr = PAGES[ACTIVE]['blocks'][bix]
		db = EDIT_DEF[gr][str(FOCUS['pix'])]
		name = db['name']
		if name in ['on','sh']: e = 1 if e>0 else -1

		v0 = EDIT_VALS[gr+'_'+ str(bix)][name] 		
		while True: # using break to exit
			val = v0 + e * 10**int(FOCUS[name])

			# compensate for single limitation
			if val > db['max']*.9999: 
				val = db['max']
				break
			# if the current digit/factor makes overshoot min: try with small e 
			# when e down to zero, if still overshooting: reduce digit/factor 
			elif val < db['min']*1.0001: 
				if e>1: e -= 1
				else: 
					if db['type'] in ['f','i']: self.ChangeSelDigit(-1)
					self.DrawParam(bix, int(FOCUS['pix']), gr)
					val = v0
					break
			else: break

		# TBD add callback to update sig gen with changed param
		if val != v0:
			EDIT_VALS[gr+'_'+ str(bix)][name] = val
			self.DrawParam(bix, int(FOCUS['pix']), gr)
			if name=='Brightness': tft.led(val)
			if name=='sh':	
				# if shape was or becomes square, redraw page to add remove Duty Cycle as needed
				if round(v0)==1 or round(val)==1: 
					self.DrawBlock(bix)

	def ProcessKnobs(self):
		# new btns value 
		btns = self.enc[0].Btn() + (self.enc[1].Btn() << 1)

		# check knob press
		if self.btn_wait0:
			if btns == 0: 
				self.btn_wait0 = False  # done waiting for release 
				self.btns = 0
		elif btns > self.btns:
			self.btns = btns
			self.btn_t0 = time.ticks_ms()
		elif btns>0 and btns == self.btns: 
			if time.ticks_diff(time.ticks_ms(), self.btn_t0) > LONG_BTN_MS:
				self.ExecKnobPress(btns, True)
		elif btns == 0 and self.btns > 0: # released :: short press
			self.ExecKnobPress(self.btns)
			self.btns = 0
		
		# E1: value change if turning knob fast, |e| can be > 1
		e = self.enc[0].GetTurn()
		if e and self.enc[0].Btn() == 0: self.ChangeValue(e)

		# E2, param change or digit change 
		e = self.enc[1].GetTurn()
		if e and self.enc[1].Btn() == 0: 
			if self.E2Mode == 'Param': self.ChangeSelPar(e)
			else: self.ChangeSelDigit(-e)

		return False

if __name__ == '__main__':
	print('\33c',end='') # clear screen in most terminals

	tst = SGUI()
	# print(EDIT_VALS,'\n')
	#print(EDIT_DEF)
	#print(FOCUS,'\n',ACTIVE)
	
	tst.ShowPage('Top')

	while True:	
		chng = tst.ProcessKnobs()
		if chng: print(chng)
		time.sleep_ms(100)

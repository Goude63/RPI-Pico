machine.freq(250_000_000)
from ST7735 import TFT
from CLT1100 import CLT1100
from f_sys	 import f_sys
from f_10x14 import f_10x14
from machine import SPI,Pin
import time

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
# Note: defd is the equivalent power of 10 0 for unit digit, -1 for first decimal digit
EDIT_DEF =  {  # defaults: defv:0, defd:0, res:min (1 for type i), color: white
'Ch': {
	'0': {'name':'on',   'type':'b','min':0,   'max':1,  'u':'',  'res' :1},
	'1': {'name':'shape','type':'w','min':0,   'max':4,  'u':'',  'res' :1},
	'2': {'name':'Fr', 'type':'f','min':0.1, 'max':5e6,  'u':'Hz','defd':2,  'color':TFT.BLUE,'defv':1000},
	'3': {'name':'Am', 'type':'f','min':1e-3,'max':10,   'u':'V', 'defv':1,  'color':TFT.PURPLE},
	'4': {'name':'Of', 'type':'f','min':-10, 'max':10,   'u':'V', 'defd':-3, 'res'  :1e-3, 'color':TFT.ORANGE},
	'5': {'name':'Ph', 'type':'i','min':-181,'max':180,  'u':'o', 'defd':1,  'color':TFT. GRAY}},
'Cfg': {
	'0':{'name':'Brightness', 'type':'i','min':0, 'max':100, 'u':'%', 'defv':75,},
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
ZOOM = True

# returns (param name, string value including units, color
# cofs = horizontal 1st character display offset, ei = index in string where focus is) 
# @micropython.native
def gformat(bix, pix, g):
	spix = str(pix)
	pix=int(pix); bix = int(bix)
	p = EDIT_DEF[g][spix]['name']
	v = g + '_' + str(bix)               # variable / value e.g. Ch_1
	color = EDIT_DEF[g][spix]['color']
	
	# initial ei value relative to decimal point (changed later to offset in string)
	ei = -int(FOCUS[p])-1 if FOCUS['block'] == bix and FOCUS['pix'] == pix else None
	# print(p, FOCUS['block'], bix, FOCUS['pix'], pix, ei, FOCUS['block'] == bix, FOCUS['pix'] == pix, type(bix), type(pix) )

	# print(v,p)
	raw =EDIT_VALS[v][p] # ['value']
	s=''; sh = 0
	u = EDIT_DEF[g][spix]['u']
	
	p = p+':'
	if u == 'Hz':
		p =''
		if raw>=1e6   	: s = f'{raw/1e6:7.3f}'; u='MHz'; sh = 6
		elif raw>1000 	: s = f'{raw/1e3:7.3f}'; u='KHz'; sh = 3
		else			: s = f'{raw:7.1f}';     u=' Hz'; sh = 0
	elif u == 'V':
		if raw<0.1	: s = f'{raw*1000:3.0f}'; u=' mV'; sh = -3 
		else		: s = f'{raw:5.3f}'; sh = 0
	elif u == 'o':
		s = f'{raw:3.0f}'; sh = 0
	
	# adjust edit character index from left of string
	if ei is None: 
		ei = -1 # not focused param
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
				if not 'color' in EDIT_DEF[grp][pix]: EDIT_DEF[grp][pix]['color'] = TFT.WHITE

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
 
	#@micropython.native
	def DrawParam(self, bix, pix, g, rof = -1.0, xof = 0, yof = 0):
		(h, s, c, ei) = gformat(bix, pix, g)
		
		pn = EDIT_DEF[g][str(pix)]['name']

		# print(f'{bix}/{pix}', end = ',' if bix<3 or pix<'5' else '\n')
		color = tft.WHITE
		col=0; row=0
		layout = PAGES[ACTIVE]['layout']

		if rof<0:
			if layout =='2x2':
				if not ZOOM: 
					xof = (bix%2)*(PIXWIDTH//2); yof = (bix//2)*(PIXHEIGHT//2)
				rof = 0.5 + int(pix)
			else:
				rof = 2 + int(pix)

		if ZOOM or layout =='1': 
			div = 1; fix = 1; fw = FW[1]; fh = FH[1]
		else:
			div = 2; fix = 0; fw = FW[0]; fh = FH[0]

		if int(pix)==0:	
			tft.fillrect((xof+col*fw,yof+row*fh),(PIXWIDTH//div,PIXHEIGHT//div), tft.BLACK)
			if layout == '2x2':
				if not ZOOM and bix == FOCUS['block']:
					color = tft.GREEN
					tft.rect((xof+col*fw,yof+row*fh),(PIXWIDTH//div-2,PIXHEIGHT//div-1), color)
				# print block name eg. ch1, settings...
				text(0.3+col//2, 0.3 + row//2, f'{g}{bix+1}', fix+1, color, xof, yof)    
		if s:
			row += rof
			if layout =='2x2':
				s = f'{h}{s}'
				text(col+1, row, s, fix, c, xof, yof)			
			if ei>=0: 
				c ^= 0xFFFFFF
				x = xof + (col+1+ei) * fw
				y = yof + (row+1)*fh - 1
				text(col+1+ei, row, s[ei], fix, c, xof, yof)

				if self.E2Mode == 'Param': 
					tft.rect((xof+col*fw + 2, yof+row*fh - 1),(PIXWIDTH//div-6, fh + 1), tft.GRAY) 
				else: 
					tft.line((xof+fw,y),(xof+PIXWIDTH//div-fw, y),tft.BLACK)  # in erase previous digit underscore
					tft.line((x,y),(x+fw,y),tft.RED) # draw underscore
		
		if layout == '1': r = 2
		else: r = 0 if pn == 'sh' or pn == 'on' else 1
		return r

	def DrawBlock(self, bix): 
		gr = PAGES[ACTIVE]['blocks'][bix]
		
		xof=0; yof=0
		if PAGES[ACTIVE]['layout'] =='2x2':	
			rof = 1.5 
			if not ZOOM:
				xof = (bix%2) * (PIXWIDTH//2)
				yof = (bix//2) * (PIXHEIGHT//2)
		else:
			rof = 2

		for pix in sorted(EDIT_DEF[gr]):
			rof += self.DrawParam(bix, pix, gr, rof, xof, yof)

	def ShowPage(self, pg):   # e.g. call: ShowPage('Top')
		global ACTIVE, PAGE
		ACTIVE = pg
		PAGE = PAGES[pg]
		if PAGE['layout'] =='2x2':
			FOCUS['block'] = self.savebix
			FOCUS['pix'] = self.savepix
			if ZOOM: 
				self.DrawBlock(FOCUS['block']) 
			else: 
				for i in range(4): self.DrawBlock(i)
		else: 
			self.savebix = FOCUS['block']
			self.savepix = FOCUS['pix']
			FOCUS['block'] = 0
			FOCUS['pix'] = 0
			self.DrawBlock(0) # Cfh page has just one block
			
	def ChangeSelPar(self, delta):
		if delta == 0: return

		# TBD update to support config page too
		newix = FOCUS['pix'] + delta
		if   newix > len(EDIT_DEF['Ch']): newix = 0
		elif newix < 0: newix = len(EDIT_DEF['Ch']) - 1

		# TBD update to support config page too
		FOCUS['pix'] = newix
		self.DrawBlock(FOCUS['block'])

	def ChangeSelDigit(self, delta):
		db = EDIT_DEF['Ch'][str(FOCUS['pix'])]
		d0 = FOCUS[db['name']] 
		d =d0 + delta

		# limit digit according to parameter max/min values
		res = db['res']
		while 10**d < res and d<9: d += 1 
		while 10**d >= db['max'] and d>-3: d -= 1

		print(d0,d)
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
				self.ShowPage(ACTIVE)
			elif knob == 3:
				np = {'Top':'Cfg','Cfg':'Top'}[ACTIVE]
				self.ShowPage(np) # toggle
		else:
			if knob == 1:  # top nom / E1 
				if ACTIVE=='Top': self.NextChannel()
			else:
				if self.E2Mode == 'Param':
					self.E2Mode = 'Digit'
				else:  # 'Digit'
					self.E2Mode = 'Param'
				self.DrawBlock(FOCUS['block'])

	def ProcessKnobs(self):
		# new btns value 
		btns = self.enc[0].Btn() + (self.enc[1].Btn() << 1)
		# if btns: print(btns, end = ' ' )

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
		
		e = self.enc[0].GetTurn()

		if e: # E1: value change if turning knob fast, |e| can be > 1
			gr = PAGES[ACTIVE]['blocks'][FOCUS['block']]
			while True: # using break to exit
				db = EDIT_DEF[gr][str(FOCUS['pix'])]
				name = db['name']
				val = EDIT_VALS[gr+'_'+ str(FOCUS['block'])][name] + e * 10**int(FOCUS[name])

				# if the current digit/factor makes overshoot min/max: try with small e 
				# when e down to zero, if still overshooting: reduce digit/factor 
				if db['min']*.99999 <= val <= db['max']*1.000001:  # compensate for single limitation
					EDIT_VALS[gr+'_'+ str(FOCUS['block'])][name] = val
					print(val)
					self.DrawParam(int(FOCUS['block']), int(FOCUS['pix']), gr)
					break
				elif e>1: 
					e -= 1
				else:
					self.ChangeSelDigit(-1)
					break

		e = self.enc[1].GetTurn()
		if e: # E2, param change or digit change 
			if self.E2Mode == 'Param': self.ChangeSelPar(e)
			else: self.ChangeSelDigit(-e)

		return False

if __name__ == '__main__':
	print('\33c',end='') # clear screen in most terminals

	tst = SGUI()
	#print(EDIT_VALS,'\n')
	#print(EDIT_DEF)
	#print(FOCUS)
	tst.ShowPage('Top')

	while True:	
		chng = tst.ProcessKnobs()
		if chng: print(chng)
		time.sleep_ms(100)



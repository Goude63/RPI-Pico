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
FW = (f_sys["Width"] + 1, f_10x14["Width"] + 2) # the tft.text function adds 1 pixel between 5 pic characters 
FH = (f_sys["Height"] + 1, f_10x14["Height"] + 2)
FONTS = (f_sys, f_10x14)  # second font must be double size of font1
PIXWIDTH	= 160
PIXHEIGHT	= 128
CARWIDTH	= PIXWIDTH // FW[0]
CARHEIGHT	= PIXHEIGHT // FH[0]
ROTATION	= 1
LONG_BTN_MS	= 500

# information for editing items. Note: defd =0 means first digit after decimal point
EDIT_DEF =  {  # defaults: defv:0, defd:1, res:min, color: white
'Ch': {
	'0': {'name':'on',   'type':'b','min':0,   'max':1,  'u':'',  'res' :1},
	'1': {'name':'shape','type':'w','min':0,   'max':4,  'u':'',  'res' :1},
	'2': {'name':'fr', 'type':'f','min':0.1, 'max':5e6,'u':'Hz','defd':3,  'color':TFT.BLUE,'defv':1000},
	'3': {'name':'am', 'type':'f','min':1e-3,'max':10, 'u':'V' ,'defv':1,  'color':TFT.PURPLE},
	'4': {'name':'of', 'type':'f','min':-10, 'max':10, 'u':'V' ,'defd':-2, 'res'  :0.1, 'color':TFT.ORANGE},
	'5': {'name':'ph', 'type':'f','min':-180,'max':180,'u':'o', 'defd':2,  'res'  :0.1, 'color':TFT. GRAY}},
'Cfg': {
	'0':{'name':'Brightness', 'type':'f','min':0, 'max':100, 'u':'%', 'defv':75},
	'1':{'name':'Volt Limit', 'type':'f','min':1, 'max':10,  'u':'V', 'defv':3,'res':0.1}}}	

# Editable elements values, factor/digit, col, row, font size of current screen location
EDIT_VALS = {}
PAGES = { 'Top':{'layout':'2x2', 'blocks':['Ch'] * 4 }}
# FOCUS / DIGIT info
FOCUS  = {'block':0,'param':'fr'}
ACTIVE = ''
PAGE   = {}
ZOOM = False

# returns (param name, string value including units, color
# cofs = horizontal 1st character display offset, ei = index in string where focus is) 
#@micropython.native
def gformat(bix, pix, g):
	p = EDIT_DEF[g][pix]['name']
	v = g + '_' + str(bix) # variavle / value e.g. Ch_1
	color = EDIT_DEF[g][pix]['color']
	
	ei = -int(FOCUS[p])	if FOCUS['block'] == bix and FOCUS['param'] == p else None

	# print(v,p)
	raw =EDIT_VALS[v][p]['value']
	s=''; sh = 0
	u = EDIT_DEF[g][pix]['u']
	if u == 'Hz':
		if raw>=1e6   	: s = f'{raw/1e6:7.3f}'; u='MHz'; sh = 6
		elif raw>1000 	: s = f'{raw/1e3:7.3f}'; u='KHz'; sh = 3
		else			: s = f'{raw:7.1f}';     u=' Hz'; sh = 0
	elif u == 'V':
		if raw<0.1	: s = f'{p}: {raw*1000:3.0f}'; u=' mV'; sh = -3 
		else		: s = f'{p}: {raw:5.3f}'; sh = 0
	elif u == 'o':
		s = f'{p}: {raw:3.0f}'; sh = 0
	
	# adjust edit character offset from left of string
	if ei is None: 
		ei = -1
	else:
		dp = s.find('.')
		if dp<0: dp = len(s); s += '.' # add temp '.'
		ei = ei + dp + sh
		if ei>=dp and s[dp].isdigit(): ei += 1
		while not s[ei].isdigit() and ei>dp: 
			ei -= 1
			FOCUS[p] = str(int(FOCUS[p]) + 1)
		if s[len(s)-1] == '.': s = s[:-1] # remove temp '.'

	return (f'{s} {u}', color, ei)

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

		# add default params keys' EDIT_VALS (defv, res and defd)
		print(FOCUS)
		for grp in EDIT_DEF: 				# grp = 'Ch', 'cfg'...
			for pix in EDIT_DEF[grp]:		# pix = '1', '2' ...
				if not 'defv' in EDIT_DEF[grp][pix] : EDIT_DEF[grp][pix]['defv'] = 0
				if not 'res' in EDIT_DEF[grp][pix]  : EDIT_DEF[grp][pix]['res'] = EDIT_DEF[grp][pix]['min']
				if not 'color' in EDIT_DEF[grp][pix]: EDIT_DEF[grp][pix]['color'] = TFT.WHITE

				# set focus digit for all parameter types
				if 'defd' in EDIT_DEF[grp][pix]: 
					FOCUS[EDIT_DEF[grp][pix]['name']] = EDIT_DEF[grp][pix]['defd']
				else:
					FOCUS[EDIT_DEF[grp][pix]['name']] = '1'

		# create current EDIT_VALS for all parameters, and default focused digit/factor
		for grp in EDIT_DEF:
			if grp in ['Ch']:
				names = []
				for i in range(4): names.append(grp + '_' + str(i))
			else: names=[grp]

			for name in names:
				EDIT_VALS[name] = {}
				for pix in EDIT_DEF[grp]:
					pn = EDIT_DEF[grp][pix]['name']
					EDIT_VALS[name][pn] = {}
					EDIT_VALS[name][pn]['value'] = EDIT_DEF[grp][pix]['defv']
					# EDIT_VALS[name][pix]['edigit'] = EDIT_DEF[grp][pix]['defd']
 
	#@micropython.native
	def DrawParam(self, bix, pix, g, rof, xof, yof):
		(s, c, ei) = gformat(bix, pix, g)
		pn = EDIT_DEF[g][pix]['name']

		# print(f'{bix}/{pix}', end = ',' if bix<3 or pix<'5' else '\n')
		color = tft.WHITE
		col=0; row=0

		#if col<0 and PAGES[ACTIVE]['layout'] =='2x2':
		#	if ZOOM: col=0; row=0
		#	else: col = (bix%2)*(CARWIDTH//2); row = (bix//2)*(CARHEIGHT//2)

		if ZOOM: div = 1; fix = 1; fw = FW[1]; fh = FH[1]
		else: 	 div = 2; fix = 0; fw = FW[0]; fh = FH[0]

		if int(pix)==0:	
			tft.fillrect((xof+col*fw,yof+row*fh),(PIXWIDTH//div,PIXHEIGHT//div), tft.BLACK)
			if not ZOOM and bix == FOCUS['block']:
				color = tft.GREEN
				tft.rect((xof+col*fw,yof+row*fh),(PIXWIDTH//div-2,PIXHEIGHT//div-1), color)
			text(0.3+col//2, 0.3 + row//2, f'{g}{bix+1}', fix+1, color, xof, yof)    # print block name eg. ch1, settings...
		if s:
			row += rof
			text(col+1, row, s, fix, c, xof, yof)
			if ei>=0: 
				c ^= 0xFFFFFF
				x = xof + (col+1+ei) * fw
				y = yof + (row+1)*fh - 1
				text(col+1+ei, row, s[ei], fix, c, xof, yof)

				if self.E2Mode == 'Param': 
					tft.rect((xof+col*fw + 2, yof+row*fh - 1),(PIXWIDTH//div-6, fh + 1), tft.GRAY) 
				else: 
					tft.line((x,y),(x+fw,y),tft.RED)
		
		r = 0 if pn == 'sh' or pn == 'on' else 1
		return r

	def DrawBlock(self, bix): 
		gr = PAGES[ACTIVE]['blocks'][bix]
		rof = 2
		xof=0; yof=0
		if PAGES[ACTIVE]['layout'] =='2x2':	
			if not ZOOM:
				xof = (bix%2) * (PIXWIDTH//2)
				yof = (bix//2) * (PIXHEIGHT//2)

		for pix in sorted(EDIT_DEF[gr]):
			rof += self.DrawParam(bix, pix, gr, rof, xof, yof)

	def ShowPage(self,pg):   # e.g. call: ShowPage('Top')
		global ACTIVE, PAGE
		ACTIVE = pg
		PAGE = PAGES[pg]
		if PAGE['layout'] =='2x2':
			if ZOOM: 
				self.DrawBlock(FOCUS['block']) 
			else: 
				for i in range(4): self.DrawBlock(i)
	
	def ChangeSelPar(self, delta):
		if delta == 0: return

		# find pix
		par_names = []
		gr = PAGE['blocks'][FOCUS['block']]
		for pix in sorted(EDIT_DEF[gr]): par_names.append(EDIT_DEF[gr][pix]['name'])
		newix = (par_names.index(FOCUS['param']) + delta) % len(par_names)

		# apply delta clip to 0, max
		newix = min(max(0, newix),len(par_names) - 1)
		FOCUS['param'] = par_names[newix]
		self.DrawBlock(FOCUS['block'])

	def ChangeSelDigit(self, delta):
		pass

	def NextChannel(self):
		prev = FOCUS['block']
		nxt = (FOCUS['block'] + 1) % 4
		FOCUS['block'] = nxt
		if not ZOOM: self.DrawBlock(prev)
		self.DrawBlock(nxt)

	def ExecKnobPress(self, knob, long = False):
		global ZOOM
		if long:
			if knob == 1:
				ZOOM = not ZOOM
				self.ShowPage(ACTIVE)
			self.btn_wait0 = True
		else:
			if knob == 1:  # top nom / E1 
				self.NextChannel()
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
		
		e2 = self.enc[1].GetTurn()
		if e2: 
			if self.E2Mode == 'Param': self.ChangeSelPar(e2)
			else: self.ChangeSelDigit(e2)
		return False

if __name__ == '__main__':
	print('\33c',end='') # clear screen in most terminals

	tst = SGUI()
	# print(FOCUS)
	tst.ShowPage('Top')

	while True:	
		chng = tst.ProcessKnobs()
		if chng: print(chng)
		time.sleep(0.2)



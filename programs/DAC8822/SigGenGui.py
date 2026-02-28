machine.freq(250_000_000)
from ST7735 import TFT
from CLT1100 import CLT1100
from sysfont import sysfont
from machine import SPI,Pin
import time
import math
#########################################
#		Global module "Constants"		#
#########################################
# ttf setup
FW = sysfont["Width"]
FH = sysfont["Height"]
PIXWIDTH = 160
PIXHEIGHT = 128
CARWIDTH = PIXWIDTH / FW
CARHEIGHT = PIXHEIGHT / FH
ROTATION = 1

spi = SPI(0, baudrate=250_000_000, polarity=0, phase=0, 
		  sck=Pin(18), mosi=Pin(19), miso=None)
tft = TFT(spi,16,17,20,21)

# information for editing items
EDIT_DEF =  {  # defaults: defv:0, defd:1, res:min 
'Ch': {
	'0-sh': {'type':'w','min':0,   'max':4,  'u':'',  'res' :1},
	'1-fr': {'type':'f','min':0.1, 'max':5e6,'u':'Hz','defd':3,'defv':1000000},
	'2-am': {'type':'f','min':1e-3,'max':10, 'u':'V' ,'defv':1},
	'3-ph': {'type':'f','min':-180,'max':180,'u':'o', 'defd':2,'res':0.1},
	'4-on': {'type':'b','min':0,   'max':1,  'u':'',  'res' :1}},
'cfg': {
	'1-bright':{'type':'f','min':0, 'max':100, 'defv':75},
	'2-Vlimit':{'type':'f','min':1, 'max':10, 'u':'V','defv':3,'res':1}}
}	

# Editable elements values, factor/digit, col, row, font size of current screen location
EDIT_VALS = {}

PAGE = { 
	'Top':{'layout':'2x2', 'blocks':['Ch_1','Ch_2','Ch_3','Ch_4'] }
}

FOCUS = {'block':1, 'param':'2-am', 'digit':3}

def format(v,p):
	pass

# wrapper that uses character sizes as coordinates 
def text(col,row, txt, color,size):
	tft.text((col*FW, row*FH), txt, color, sysfont, size)

#TFT(spi, aDC, aReset, aCS, aLED)
class SGUI:
		# 'defv' not stated: =0. 'res' not stated: =min. defd not stated: =1
		# parameters start with a 'n-' to facilitate friendly sorted enumeration 

		
	def __init__(self): 
		tft.initr()
		tft.rotation(ROTATION)
		tft.rgb(True)
		tft.led(75)
		self.enc = (CLT1100(1, 0), CLT1100(2, 3)) # 2 encoders as UI

		# add default params keys' EDIT_VALS (defv, res and defd)
		for elem in EDIT_DEF: 					# elem = 'Ch', 'cfg'...
			for param in EDIT_DEF[elem]:		# param = 'fr', 'am' ...
				if not 'defv' in EDIT_DEF[elem][param]: 
					EDIT_DEF[elem][param]['defv'] = 0
				if not 'defd' in EDIT_DEF[elem][param]: 
					EDIT_DEF[elem][param]['defd'] = 1
				if not 'res' in EDIT_DEF[elem][param]: 
					EDIT_DEF[elem][param]['res'] = EDIT_DEF[elem][param]['min']
		
		# create current EDIT_VALS for all parameters, and default focused digit/factor
		for elem in EDIT_DEF:
			Ch = 1
			while Ch <= (4 if elem == 'Ch' else 1):  
				name = 'Ch_'+str(Ch) if elem=='Ch' else elem  # name = EDIT_DEF name + '_' + count/index

				EDIT_VALS[name] = {}
				for param in EDIT_DEF[elem]:
					EDIT_VALS[name][param] = {}
					EDIT_VALS[name][param]['value'] = EDIT_DEF[elem][param]['defv']
					EDIT_VALS[name][param]['edigit'] = EDIT_DEF[elem][param]['defd']			
				Ch += 1
 
	def DrawParam(self, v, p, col, row, fs):
		dn = p[2:] # remove the 'n-' for the parameter name			
		text(col+1, row, dn+':', tft.WHITE, fs)
		# print(v, p, EDIT_VALS[v][p]['value'])
		text(col+5, row, f'{EDIT_VALS[v][p]["value"]}' , tft.WHITE, fs)
		r = 0 if dn == 'sh' or dn == 'on' else 1
		return r

	def DrawBlock(self,ix , v, col, row, fs): 
		print(col,row)
		dfb = v.split('_')[0]  # get definition block name and 
		if dfb == 'Ch' and ix == FOCUS['block']: 
			tft.rect((col*FW,row*FH),(PIXWIDTH//2,PIXHEIGHT//2), tft.GREEN)
		text(0.5 + col, 0.5 + row, f'{dfb}{ix}',tft.WHITE, fs*2)    # print block name eg. ch1, settings...
		row += 3

		for p in sorted(EDIT_DEF[dfb]):
			row += self.DrawParam(v, p, col, row, fs)

	def ShowPage(self,pg):   # e.g. call: ShowPage(PAGE['Top'])
		tft.fill(tft.BLACK)
		if pg['layout'] =='2x2':
			for i,v in enumerate(pg['blocks']):
				self.DrawBlock(i+1, v, (i%2)*(CARWIDTH//2),(i//2)*(CARHEIGHT//2), 1)


if __name__ == '__main__':
	print('\33c',end='') # clear screen in most terminals
	tst = SGUI()
	# print(EDIT_VALS)
	# print(EDIT_VALS['Ch_1']['2-fr']['value'])
	# tft.fill(tft.BLACK)
	# print(sysfont['CARWIDTH'],sysfont['CARHEIGHT'])
	tst.ShowPage(PAGE['Top'])



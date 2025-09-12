#
# Module decoding modbus protocol for EG4 LifePower batteries 
# Hard coded for two packs (only in __init__, the rest of the code is ok)
#
from machine import UART, Pin, Timer
import micropython,array, time, json

SOI = 126
EOI = 13
STATE = ['Discharging', 'Charging', 'Unused', 'Standby'],

BPack = '{"cells" : [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0], "temps" : [0,0,0,0,0,0], '
BPack += '"curr"  : 0.0, "volt"  : 0.0,	"ah"    : 0.0,  "cap" : 0.0,	"soc"   : 0.0, "soh"   : 0.0, '
BPack += '"state" : 2, "maxcv"  : 0, "mincv" : 0, "overv" : 0, "underv" : 0, "balance" : 0 }'

class LifePower(object):
	TX_REP = 3
	SELF = None # static var to hold instance used in timer callback
	TX_MSG = ['~20004A420000FDA3\r', '~20004A440000FDA1\r',
		'~20024A420000FDA1\r', '~20024A440000FD9F\r' ]
	@staticmethod
	@micropython.native
	def pool_uart(tmr):
		micropython.schedule(LifePower.SELF.irq_rx, 0)

	def __init__(self, tx=4):
		if (tx<=8):	uid = 1
		else: uid = 0

		self.uart = UART(uid, baudrate=19200,
			tx=Pin(tx), rx=Pin(tx+1),
			txbuf=64, rxbuf=1024, timeout_char=0,
			timeout=0, stop=1)
		self.rx_buf  = bytearray(256)
		self.msg = bytearray(256)
		self.msg_len = 0
		self.next_tx = time.ticks_ms() # now
		self.tx_ix = 0
		self.retry = 0
		self.got_msg = False
		self.DumpMsg()

		# to de-hard code for two battery packs, change this line...
		self.Pack = [json.loads(BPack) ,json.loads(BPack)] # two packs in my setup

		LifePower.SELF = self
		self.pool_tmr = Timer(period = 50, callback=LifePower.pool_uart)
	
	# called from timer irq, through 'schedule'
	@micropython.native
	def irq_rx(self, z):
		while self.uart.any() > 0:
			c = ord(self.uart.read(1))
			if (c == SOI): 
				self.rx_ix = 1
				self.rx_buf[0] = SOI
			# ignore bytes if SOI not there
			elif (self.rx_ix > 0): 
				self.rx_buf[self.rx_ix] = c
				self.rx_ix += 1
				
				# validate ~20 (20)
				if self.rx_ix == 3:
					if self.rx_buf[1] != 0x32 or self.rx_buf[2] != 0x30:
						self.DumpMsg()

				# verify len checksum (dump msg if not ok)
				elif self.rx_ix == 13: 
					self.VerHeader()
				elif (c == EOI ): 
					# print('EOI received')
					if self.rx_ix > 18:
						self.msg[0:self.rx_ix] = self.rx_buf[0:self.rx_ix]
						self.msg_len = self.rx_ix
						self.ifo_len = self.len
					self.DumpMsg()

				elif self.rx_ix > self.len + 18: 
					print("missing EOI")
					self.DumpMsg()
				# else:	print(self.rx_ix,end='-')

	@micropython.native
	def DumpMsg(self):
		self.len = 0xFFFFFF
		self.rx_ix = 0

	@micropython.native
	def VerHeader(self):
		buf = self.rx_buf # equivalent to "with self.rx_buf"
		# verify 4A xx 00
		# print(buf[0:14])
		if not (buf[5] == 0x34 and buf[6] == 0x41 and 
		          buf[7] == 0x30 and buf[8] == 0x30):
			self.DumpMsg()
			return
		# verify len checksum
		hexlen = buf[10:13].decode('ascii')
		msg_chk = int('0x' + buf[9:10].decode('ascii'))
		chk = 0
		for ix in range(0,3): chk += int('0x' + hexlen[ix])
		chk = ((chk ^ 15) + 1) & 15
		# print('len chksum:', chk, ' vs ', msg_chk,
		#	' ix= ', self.rx_ix, '\r\nhex=', self.rx_buf[:13].decode('ascii'))
		if (msg_chk != chk): self.DumpMsg()
		else: 
			l = int("0x" + hexlen)
			if l <= 202: self.len = l
			else: self.DumpMsg()
			# print("len = ", self.len, hexlen)

	# must be epriodically called (not executed in irq/schedule )
	@micropython.native
	def ProcessMsg(self):
		if self.msg_len == 0: 
			# when no message pending, send Analog/Alarm requests
			now = time.ticks_ms()			
			if self.got_msg or (self.retry > LifePower.TX_REP):
				# received a message, take a 3s break
				self.tx_ix = (self.tx_ix + 1) % 4 # prepare next request
				self.got_msg = False
				self.retry = 0
				self.next_tx = now
				if self.tx_ix == 0: self.next_tx += 15000
			elif ((time.ticks_diff(self.next_tx, now) < 0) and 
				(self.rx_ix == 0) and (self.uart.any() == 0)):
				# no reply within 350 ms, ask again
				self.next_tx = now + 350
				print(self.tx_ix, end='') # show current ix
				self.uart.write(LifePower.TX_MSG[self.tx_ix].encode('ascii'))
				self.retry += 1
			return
		'''
		print("\r\nNew msg: len=",self.ifo_len, 
		 "\r\nmsg=", self.msg[0:19].decode('ascii'),
		  " ... ", self.msg[self.msg_len-10:self.msg_len-1].decode('ascii'), )
		'''
		if not self.VerChkSum():
			print('Bad message checksum') 
			self.msg_len = 0 # dump bad msg
			return

		r = False
		try: addr = int('0x' + self.msg[3:5].decode('ascii'))
		except: addr = -1
		if addr >= 0:
			#print('raw addr:', addr, end ='  ')
			if addr > 1: addr -= 1 # addr 1 = EG4. Pack: 0, 2, 3 ... 
			#print('pack_no:', addr)
			Pack = self.Pack[addr]
			if   (self.ifo_len == 84 ): r = self.ParseAlarms(Pack)
			elif (self.ifo_len == 202): r = self.ParseAnalog(Pack)
			self.msg_len = 0 # done with message
			#print(addr, Pack)
			self.got_msg = r
		return r

	@micropython.native
	def VerChkSum(self):
		sum = 0
		for ix in range(1,self.msg_len - 5): sum += self.msg[ix]
		sum = ((sum ^ 0xffff) + 1) & 0xffff
		csix = self.msg_len - 5
		try: msgchk = int("0x" + self.msg[csix:csix+4].decode('ascii'))
		except: msgchk = sum - 1 # wrong...
		# print("Msg chk sum: ", sum, " vs ", msgchk)		
		return sum == msgchk
	
	# note the two next functions ARE NOT called from irq/scedule
	@micropython.native
	def ParseAnalog(self, Pack):
		buf = self.msg

		# decode cells voltage (in mv)
		a = Pack['cells']
		for i in range(0,16):
			xi = 19 + i*4
			a[i] = int('0x' + buf[xi:xi+4].decode('ascii'))

		# decode misc temperatures
		a = Pack['temps']
		for i in range(0,6):
			xi = 85 + i*4
			k = int('0x' + buf[xi:xi+4].decode('ascii'))
			a[i] = (k-2731) / 10
		
		# decode global pack values
		gp = array.array('f', [0.0]*4)
		for i in range(0,4):
			xi = 109 + i*4
			x = int('0x' + buf[xi:xi+4].decode('ascii'))

			#handle negative current
			if i == 0 and x >= 0x8000:
				x = -((x ^ 0xFFFF) + 1) # 2's complement

			gp[i] = x/100

		Pack['curr']  = gp[0]
		Pack['volt']  = gp[1]
		Pack['ah']    = gp[2]
		Pack['cap']   = gp[3]

		# decode the rest
		gp = array.array('H', [0]*4)
		for i in range(0,4):
			xi = 131 + i*4
			gp[i] = int('0x' + buf[xi:xi+4].decode('ascii'))
		Pack['soc']    = gp[0]
		Pack['soh']    = gp[1]
		Pack['maxcv']  = gp[2]
		Pack['mincv']  = gp[3]
		return True
		
	@micropython.native
	def ParseAlarms(self, Pack):
		buf = self.msg
		ovr = 0 
		undr = 0

		# decode over and under voltage
		for i in range(0,16):
			xi = 19 + i*2
			w = int('0x' + buf[xi:xi+2].decode('ascii'))
			if   w == 1: undr = undr or 2**i
			elif w == 2: ovr = ovr or 2**i
		Pack['overv'] = ovr
		Pack['underv'] = undr		

		# decode balancing flags and state
		xi = self.msg_len - 13
		Pack['state'] = int('0x' + buf[xi:xi+2].decode('ascii'))
		Pack['balance'] = int('0x' + buf[xi+2:xi+6].decode('ascii'))

		return True
		
if __name__=='__main__':
	machine.freq(250000000)
	lp = LifePower()
	while True: 
		time.sleep_ms(200)
		if lp.ProcessMsg():
			s = json.dumps(lp.Pack)
			print('Packs:', s)



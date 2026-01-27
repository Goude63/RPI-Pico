# uart communication using ascii and Pico USB port
# including minimal parsing functions

import sys,select

class USBCOM(object):
	def __init__(self, StartSymb=b'#', EndSymb=b'*', BufSize=128, DisableCtrlC=False):
		self.BufSize = BufSize
		self.Buf = bytearray(BufSize)  # Buf will hold one message excluding Start/End Symbols
		self.Start = StartSymb
		self.End = EndSymb
		self.BufCnt = -1    # buffer is empty

		if DisableCtrlC: micropython.kbd_intr(-1)
	
	# scan input and return commands (inside Start/End symbols)
	# returns Non
	def Scan(self):
		r=""
		while select.select([sys.stdin],[],[],0)[0]:
			rb = sys.stdin.buffer.read(1)
			print(rb.decode('utf-8'),end='')
			if (rb == self.Start): 
				self.BufCnt = 0
			elif self.BufCnt >= 0: # Only gather data after StartSymb
				if (rb==self.End):
					r=self.Buf[:self.BufCnt].decode('utf-8')
				else:
					self.Buf[self.BufCnt] = rb[0]
					self.BufCnt += 1
					if(self.BufCnt >= self.BufSize):
						self.BufCnt = -1
						sys.stdout.buffer.write(self.Start + b'Err:Command too long' + self.End + b'\r\n')


		return r


# test
if __name__ == "__main__":
	usb = USBCOM()
	while(True):
		msg=usb.Scan()
		if (msg): print('\r\n',msg)


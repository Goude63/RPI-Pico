import rp2, time, network, socket, ubinascii, urequests, random

class WiFi:
	def __init__(self, host='', country='CA', dbghost = ['legion.local', 'cell']):
		if host == '': host = 'PicoW' + str(random.getrandbits(16))
		rp2.country(country)
		network.hostname(host)
		self.wlan = network.WLAN(network.STA_IF)
		if isinstance(dbghost, str): self.dbghost = [dbghost]
		else: self.dbghost = dbghost # UDB debug terminal (first found will be used)

	def Connect(self, ssid = '', pw =''):
		if ssid == '': ssid = self.ssid; pw = self.pw # re-connect
		else: self.ssid =ssid; self.pw = pw

		self.wlan.active(True) 
		self.wlan.connect(ssid, pw)

		n = 0
		while self.wlan.status() > 0 and self.wlan.status() < 3 and n < 30:
			time.sleep(1)
			n += 1
			print('*', end = '')
		
		if self.wlan.status() == 3:
			self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP 
			mac = ubinascii.hexlify(self.wlan.config('mac'),':').decode() 
			
			# look for UDP debug targets
			self.dbglst = [] # no debug targets yet			
			for d in self.dbghost:
				try: 
					ip =  socket.getaddrinfo(d, 0) [0][-1][0]
					self.dbglst.append(ip)
				except: print('Not found:', d)

			print('Mac=', mac, ' IP=', self.wlan.ifconfig()[0], ' dbgaddr=' , self.dbglst)
		else:
			print(self.wlan.status())
	
	# wrapper for ease of use
	def disconnect(self): self.wlan.disconnect()
	def status(self): return self.wlan.status()
	def rssi(self): return self.wlan.status('rssi')

	# UDP terminal debug logger
	def DoLog(self, msg, end='\r\n'):
		msg += end

		for ip in self.dbglst:
			try: self.sock.sendto(msg.encode('ascii'), (ip, 4321))
			except: pass

if __name__ == "__main__":
	wifi= WiFi('PicoLogCarBat','CA','cell')
	wifi.Connect('marc', 'bonjourlapolice')

	rec = False
	while True:
		if  wifi.status() != 3:
			wifi.disconnect()
			wifi.Connect()
			rec = True
		if wifi.status() == 3:
			if rec: wifi.DoLog('Re-connected', ' '); rec = False			
			wifi.DoLog('rssi=' + str(wifi.rssi()) + " dBm")
		time.sleep(15)
		machine.reset() # test for reboot mode on next send


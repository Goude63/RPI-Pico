# input pins for ws_pico_2

from machine import Pin

class Buttons():
	def __init__(self):
		self.name = "ws_pico"
		self.key1 = Pin(2, Pin.IN, Pin.PULL_UP)
		self.key2 = Pin(3, Pin.IN, Pin.PULL_UP)
		self.key3 = Pin(0, Pin.IN, Pin.PULL_UP)
		self.key4 = Pin(15, Pin.IN, Pin.PULL_UP)

		self.up_left = self.key1
		self.up_right = self.key2
		self.down_left = self.key3
		self.down_right = self.key4


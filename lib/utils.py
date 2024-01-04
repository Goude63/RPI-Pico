import uctypes

# show hex with limit on n bits (for negative values)
def hexn(x, n=32):
	return hex(x & (2**n-1))

def field(w32, b0, size):
	mask = (2**size) - 1
	return (w32 >> b0) & mask


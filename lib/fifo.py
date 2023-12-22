class FIFO(object):
    def __init__(self, size):
        self.buffer=bytearray(size)
        self.bmv = memoryview(self.buffer)
        self.size  = size
        self.count = 0
        self.wr_ix = 0
        self.rd_ix = 0
        
    def write(self, mvd):
        l = len(mvd)
        if l > self.size - self.count: return False
        self.count += l
        
        #case where data needs to be wrapped
        if self.wr_ix + l > self.size:
            cnt = self.size - self.wr_ix # len of part 1
            self.bmv[self.wr_ix: self.size] = mvd[0:cnt] #to wrap
            self.bmv[0: l-cnt] = mvd[cnt: l] #to wrap
        else:
            #case with no wrapping
            self.bmv[self.wr_ix: self.wr_ix + l] = mvd[0:l]
        
        self.wr_ix = (self.wr_ix + l) % self.size                
        return True
    
    def read(self, l=-1):
        if l < 0: l=self.size=self.count
        if l > self.count: l = self.count 
        r = bytearray(l)
        rv = memoryview(r)
        if self.rd_ix + l > self.size:
            cnt = self.size - self.rd_ix
            rv[0:cnt] = self.bmv[self.rd_ix: self.size]
            rv[cnt:l] = self.bmv[0:l-cnt]
        else:
            rv[0:l] = self.bmv[self.rd_ix: self.rd_ix + l]
        
        self.count -= l
        self.rd_ix = (self.rd_ix + l) % self.size
        return r

#test it
    
f = FIFO(25)
for n in range(20):
    if not(f.write(memoryview(b'Bonjour!'))):print("*")
    print(f.read(5))

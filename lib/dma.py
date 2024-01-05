#
# Gathered from various internet examples with minor modifications
# Example at the end. Add # on ''' lines 99 and 141 to activate demo 
#
import uctypes
from utils import *
from machine import mem32
class Dma:    
    # Some constants
    BASE_DMA  = 0x50000000
    ABORT_REG = BASE_DMA + 0x444

    FREE_DMA = list(range(12)) # by default, all DMA ch available
	
    # if some DMA channels are used by something else, exclude them here
    @staticmethod
    def ExcludeDMA(list): 
        for x in list: SigGen.FREE_DMA.remove(x)
    
    # ch -1 means auto choose available channel
    def __init__(self, ch=-1, data_size = 1):
        if ch<0: 
            if len(Dma.FREE_DMA) == 0: raise(Exception('No DMA channel available')) 
            ch = Dma.FREE_DMA.pop(0)
        else:
            if not(ch in Dma.FREE_DMA): raise(Exception('DMA channel #' + str(ch) + ' not available')) 
            Dma.FREE_DMA.remove(ch)

        offset = ch * 0x40
        self.ch = ch
        self.ReadRegister = Dma.BASE_DMA + offset
        self.WriteRegister = Dma.BASE_DMA + 4 + offset
        self.CntReg = Dma.BASE_DMA + 8 + offset
        self.TrigCtrlReg = Dma.BASE_DMA + 0xC + offset
        self.CtrlReg = Dma.BASE_DMA + 0x10 + offset
        self.CtrlVal = 0x3F8033 #so that the chain value is set to itself
        self.SetDataSize(data_size)
        self.ChainTo(ch)

    @staticmethod
    @micropython.viper
    def Abort(chs): # integer or list of channels to 
        ptr = ptr32(Dma.ABORT_REG)
        bits = 0
        if type(chs) == type([]):
            for ch in chs: bits |= 2 ^ uint(ch)
        else:
            bits = 1 << uint(chs)
        ptr[0] = bits
        while ptr[0] != 0: pass  # wait all ch aborted
        
    @micropython.viper
    def SetWriteadd(self, add: uint):
        ptr= ptr32(self.WriteRegister)
        ptr[0] = add
        #self.Writeadd = add
        
    @micropython.viper
    def SetReadadd(self, add: uint):
        ptr= ptr32(self.ReadRegister)
        ptr[0] = add
        #self.Readadd = add
        
    @micropython.viper
    def SetCnt(self, count: uint):
        ptr= ptr32(self.CntReg)
        ptr[0] = count
        #self.TransferCount = count
        
    @micropython.viper
    def SetCtrlReg(self, CtrlVal: uint):
        ptr= ptr32(self.CtrlReg)
        ptr[0] = CtrlVal
        self.CtrlVal = CtrlVal
        
    @micropython.viper
    def SetTrigCtrlReg(self, CtrlVal: uint):
        ptr= ptr32(self.TrigCtrlReg)
        ptr[0] = CtrlVal
        self.CtrlVal = CtrlVal
    
    def Trigger(self):
        mem32[self.TrigCtrlReg] = self.CtrlVal
            
    def ChainTo(self, ChainCh: uint):
        self.CtrlVal &= ~0x7800
        self.CtrlVal |= (ChainCh << 11)
    
    def SetWrap(self, nbits: uint, rw01: uint):
        self.CtrlVal &= ~0x7c0
        self.CtrlVal |= (nbits << 6) | (rw01 << 10)
        
    def SetDataSize(self, size: uint):  # size = 1, 2 or 4
        self.CtrlVal &= ~0xC
        self.CtrlVal |= (size >> 1) << 2
    
    def SetDREQ(self, dreq: uint):
        self.CtrlVal &= ~0x1f8000 # bits 21:15
        self.CtrlVal |= dreq << 15

    # enables but does not trigger (force apply all CtrlVal setting)
    def Enable(self, En_0_1 = 1):
        self.CtrlVal &= ~1
        self.CtrlVal |= En_0_1
        mem32[self.CtrlReg] = self.CtrlVal

    # 0:don't,  1: do increment,
    def SetAddrInc(self, rdInc = 1, wrInc = 1):
        self.CtrlVal &= ~0x30 # bits 5:4
        self.CtrlVal |= ((wrInc << 1) | rdInc) << 4

    def Info(self, title=''):
        if (title): print(title)
        ch = self.ch        
        ctrl = mem32[self.CtrlReg]
        print('ch:', ch, ' ctrl:', hex(ctrl)[2:], ' Size:', 2**field(ctrl,2,2), ' EN:', ctrl & 1, \
            ' BUSY:', field(ctrl,24,1), ' TREQ:', field(ctrl,15,6), end='  ')
        chain = field(ctrl,11,4)
        if chain == ch: chain = '-'
        print('Chain:',chain)
        print('Read:',hex(mem32[self.ReadRegister])[2:],end='  ')
        print('Write:',hex(mem32[self.WriteRegister])[2:],end='  ')
        print('Cnt:',str(mem32[self.CntReg]) + '/' + str(mem32[Dma.BASE_DMA + 0x804 + 0x40 * ch]),end='  ')
        print('INC_R-W:', str(field(ctrl,4,1))+ '-' + str(field(ctrl,5,1)), \
            ' RING:', str(2**field(ctrl,6,4)) +  '-' + 'RW'[field(ctrl,10,1)], '\n')
              
    @micropython.native
    def SetChData(self, src, dst, count: uint, trigger : bool):
        mem32[self.ReadRegister] = uctypes.addressof(src)
        mem32[self.WriteRegister] = uctypes.addressof(dst)
        mem32[self.CntReg] = count
        if trigger: self.Trigger()

    def DeInit(self):
        self.__del__()

    def __del__(self):
        if not (self.ch in Dma.FREE_DMA): 
            Dma.FREE_DMA.append(self.ch)

'''
def tst():
    global Dma0, Dma1
    print('\33c') # clear screen

    n = 40 # must be > 20
    a = bytearray(n)
    b = bytearray(n)
    c = bytearray(n)

    for x in range (n): a[x]= x
    for x in range (n): b[x]= 0xbb
    for x in range (n): c[x]= 0xcc

    Dma0 = Dma() 
    Dma1 = Dma()
    Dma1.Enable() # Chain will not work if chained channel is not enabled
    Dma0.ChainTo(1)

    # read location, write location, number of transfers, Trigger transfer?
    # This example illustrates chaining channels 0->1

    Dma1.SetChData(b, c, n-10, False)

    print('Before transfers:')
    print('a=',a.hex())
    print('b=',b.hex())
    print('c=',c.hex())
    print()

    Dma0.SetChData(a, b, n-20, True)
    # Dma1.SetChData(b, c, n-10, True)  # should no be needed (unless chain don't work)

    print('After transfers:')
    print('a=',a.hex())
    print('b=',b.hex())
    print('c=',c.hex(),end='\n\n')

    Dma0.Info()
    Dma1.Info()

    Dma0.DeInit()
    Dma1.DeInit()
tst()
'''

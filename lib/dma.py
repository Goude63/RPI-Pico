class Dma:    
    # Some constants
    BASE_DMA  = 0x50000000
    ABORT_REG = BASE_DMA + 0x444    
    
    def __init__(self, ch, data_size = 1):
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
        print(ptr[0])
        print(bits)
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
    
    @micropython.viper
    def TriggerChannel(self):
        ptr= ptr32(self.TrigCtrlReg)
        ptr[0] = uint(self.CtrlVal)
            
    def ChainTo(self, ChainCh : uint):
        self.CtrlVal &= ~0x7800
        self.CtrlVal |= (ChainCh << 11)
        
    def SetDataSize(self, size: uint):  # size = 1, 2 or 4
        self.CtrlVal &= ~0xC
        self.CtrlVal |= (size >> 1) << 2
              
    @micropython.viper
    def SetChData(self, readadd : uint , writeadd : uint, count: uint, trigger : bool):
        ptr= ptr32(self.ReadRegister)
        ptr2= ptr32(self.WriteRegister)
        ptr3= ptr32(self.CntReg)
        ptr[0] = readadd
        ptr2[0] = writeadd
        ptr3[0] = count
        if trigger:
            ptr4= ptr32(self.TrigCtrlReg)
            ptr4[0] = uint(self.CtrlVal)

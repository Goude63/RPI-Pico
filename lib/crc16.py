
@micropython.native
def crc16(data: bytearray, l=None, AddChkSum = True, poly=0xA001):
    if l is None: l=len(data)
    mv = memoryview(data)
    crc = 0xFFFF
    for ix in range(0,l):
        cur_byte = data[ix] ^ crc
        for _ in range(0, 8):
            if (cur_byte & 0x0001):
                cur_byte = (cur_byte >> 1) ^ poly
            else:
                cur_byte >>= 1            
        crc = cur_byte
    crc &= 0xFFFF
    crc = (crc << 8) | ((crc >> 8) & 0xFF)

    # add crc to current message (if there is room)
    # there will be an exception if data is immutable
    if AddChkSum and len(data) >= l + 2:  
        data[l]   = crc >> 8
        data[l+1] = crc & 0xFF
    
    return crc & 0xFFFF

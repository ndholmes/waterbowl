from smbus2 import i2c_msg

class mcp3427:
  bus = None
  address = 0x00
  confByte = 0x98
  
  def __init__(self, bus, address):
    self.bus = bus
    self.address = address

  def configure(self, continuousConversion = True, channel = 1, gain = 1, bitDepth = 16):
    self.confByte = 0x00
    if continuousConversion is True:
      self.confByte |= 0x10
    
    self.confByte |= [0x00, 0x20, 0x40, 0x60][channel-1]
    if bitDepth is 16:
      self.confByte |= 0x08
    elif bitDepth is 14:
      self.confByte |= 0x04
    elif bitDepth is 12:
      pass
    else:
      raise Exception('Illegal bit depth - must be 12, 14, or 16')
      
    if gain is 1:
      pass
    elif gain is 2:
      self.confByte |= 0x01
    elif gain is 4:
      self.confByte |= 0x02
    elif gain is 8:
      self.confByte |= 0x03
    else:
      raise Exception('Illegal gain value - must be 1,2,4,8')
    
    self.bus.write_byte(self.address, self.confByte)

  def getADCVolts(self):
    adcval = self.getADCValue()
    maxval = {0x00: 0x07FF, 0x04: 0x1FFF, 0x08:0x7FFF}[self.confByte & 0x0C]
    pgaval = [1.0, 2.0, 4.0, 8.0][self.confByte & 0x03]
    return (2.048 / pgaval) * adcval / maxval
    

  def getADCValue(self):
    read = i2c_msg.read(self.address, 3)
    self.bus.i2c_rdwr(read)
    
    bitmask = {0x00: 0x0FFF, 0x04: 0x3FFF, 0x08:0xFFFF}[self.confByte & 0x0C]
    
    bytes = list(read)
    
    raw = (bytes[0] * 256 + bytes[1])
    
    if (raw & 0x8000) != 0:
      sign = -1
    else:
      sign = 1
        
    if -1 == sign:
      raw ^= 0xFFFF
      raw += 1
    
    raw &= bitmask
    
    if -1 == sign:
      retval = raw * -1
    else:
      retval = raw
    
    return retval
    

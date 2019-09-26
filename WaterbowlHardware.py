# System imports
import sys
import time

# Hardware imports
import VL53L1X
import RPi.GPIO as GPIO
import BMX280
import mcp3427
import smbus2

class WaterbowlState:
  IDLE      = 0
  FILTERING = 1
  SETTLING  = 2
  REFILLING = 3
  WAITING   = 4
   

class WaterbowlStatus:
  tankLevel = 0
  bowlLevel = 0
  foodLevel = 0
  airTempF = 0.0
  airHumidity = 0.0
  airPressure = 0.0
  state = WaterbowlState.IDLE
  lastUpdate = 0
  
wbstatus = WaterbowlStatus()

class WaterbowlHardware:
  CIRCULATOR_PUMP = 21
  UV_STERILIZER   = 20
  INLET_VALVE     = 16
  
  FOOD_EMPTY_MM  = 250.0
  
  def __init__(self):
    self.tof = VL53L1X.VL53L1X(i2c_bus=1, i2c_address=0x29)     
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(self.CIRCULATOR_PUMP, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(self.UV_STERILIZER, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(self.INLET_VALVE, GPIO.OUT, initial=GPIO.LOW)
    print(GPIO.RPI_INFO)

  def sensorInit(self):
    self.tof.open() # Initialise the i2c bus and configure the sensor
    self.bme280 = BMX280.BMX280()
    self.adc1 = mcp3427.mcp3427(smbus2.SMBus(1), 0x68)
    self.adc1.configure(True, 1, 1, 16)
    time.sleep(0.1)
    
  def getFoodLevel(self):
    self.tof.start_ranging(1) # Start ranging, 1 = Short Range, 2 = Medium Range, 3 = Long Range
    distance_in_mm = self.tof.get_distance() # Grab the range in mm
    self.tof.stop_ranging() # Stop ranging
   
    foodPercent = 0

    if distance_in_mm >= self.FOOD_EMPTY_MM:
      foodPercent = 0
    else:
      foodPercent = (self.FOOD_EMPTY_MM - distance_in_mm) * 100.0 / self.FOOD_EMPTY_MM 
      foodPercent = int(foodPercent)
    return foodPercent

  def getTankLevel(self):
    adcv = self.adc1.getADCVolts()
    gauge = 1.0 + (1781 - (1758 * adcv) / (3.2 - adcv)) / 186.5
    
    full = 6.5
    level = int( gauge * 100.0 / full )
    return level
    

  def readAmbientConditions(self):
    return self.bme280.convert()

  def setCirculatorPump(self, state):
    if True == state:
      GPIO.output(self.CIRCULATOR_PUMP, GPIO.HIGH)
    else:
      GPIO.output(self.CIRCULATOR_PUMP, GPIO.LOW)

  def setSterilizer(self, state):
    if True == state:
      GPIO.output(self.UV_STERILIZER, GPIO.HIGH)
    else:
      GPIO.output(self.UV_STERILIZER, GPIO.LOW)
   
  def setInletValve(self, state):
    if True == state:
      GPIO.output(self.INLET_VALVE, GPIO.HIGH)
    else:
      GPIO.output(self.INLET_VALVE, GPIO.LOW)

  def close(self):
    GPIO.cleanup()

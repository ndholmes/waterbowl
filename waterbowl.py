# System imports
import sys
import time
import thread
import datetime

import WaterbowlHardware

# Web service imports 
import web

urls = (
    '/status', 'ws_status'
)

class WaterbowlState:
  IDLE      = 0
  FILTERING = 1
  SETTLING  = 2
  REFILLING = 3
  WAITING   = 4
  
class ws_status:        
  def GET(self):
    wbstatus = WaterbowlHardware.wbstatus
    output = "{ \"status\": { \n";
    output += "   \"id\": \"%d\", \n" % (id(wbstatus))
    output += "   \"tankLevel\": \"%d\", \n" % (wbstatus.tankLevel)
    output += "   \"bowlLevel\": \"%d\", \n" % (wbstatus.bowlLevel)    
    output += "   \"foodPercent\": \"%d\", \n" % (wbstatus.foodLevel)    
    output += "   \"airTempF\": \"%.1f\", \n" % (wbstatus.airTempF)
    output += "   \"airHumidity\": \"%.1f\", \n" % (wbstatus.airHumidity)
    output += "   \"barometricPressure\": \"%.1f\", \n" % (wbstatus.airPressure)
    output += "   \"state\": \"%s\", \n" % (['IDLE','FILTERING','SETTLING','REFILLING','WAITING'][wbstatus.state])
    output += "   \"update\": \"%s\" \n" % (wbstatus.lastUpdate)
    output += '}';
    return output

def delayWithStatus(hw, wbstatus, statusString, delayTimeSeconds, interval):
  timestamp = time.strftime("%d-%b-%Y %H:%M:%S")
  print "%s [%s] Delaying %d seconds, reporting every %d seconds" % (timestamp, statusString, delayTimeSeconds, interval)
  while delayTimeSeconds >= 0:
    timestamp = time.strftime("%d-%b-%Y %H:%M:%S")
    print "%s [%s] %ds remaining, Food: %d%% Tank: %d%% Temp: %.1fF" % (timestamp, statusString, delayTimeSeconds, wbstatus.foodLevel, wbstatus.tankLevel, wbstatus.airTempF)
    i = interval
    while i > 0:
      i -= 1
      startTime = time.time()
      # Update sensors
      wbstatus.foodLevel = hw.getFoodLevel()
      ambient = hw.readAmbientConditions()
      wbstatus.tankLevel = hw.getTankLevel()
      wbstatus.airPressure = ambient['pressure_sl']
      wbstatus.airTempF = ambient['temperature_f']
      wbstatus.airHumidity = ambient['humidity']
      
      wbstatus.lastUpdate = datetime.datetime.now()
      elapsedTime = time.time() - startTime
      if elapsedTime < 1.0 and elapsedTime >= 0.0:
        time.sleep(1.0 - elapsedTime)

    delayTimeSeconds -= interval
    

print "wbstatus = %d" % (id(WaterbowlHardware.wbstatus))


def main():
  wbstatus = WaterbowlHardware.wbstatus
  
  app = web.application(urls, globals())
  thread.start_new_thread(app.run, ())
  hw = WaterbowlHardware.WaterbowlHardware()
  hw.sensorInit()

  print "wbstatus = %d" % (id(wbstatus))

  try:
    while True:
      # Basic algorithm
      # Circulate for 10 minutes
      # Wait for 1 minute for draining
      # Open inlet valve for 1 minute
      # Wait for 4 hours
      if WaterbowlState.IDLE == wbstatus.state:
        wbstatus.state = WaterbowlState.REFILLING
      elif WaterbowlState.REFILLING == wbstatus.state:
        hw.setInletValve(True)
        delayWithStatus(hw, wbstatus, "\033[36mREFILLING\033[0m", 60 * 1, 10)
        hw.setInletValve(False)
        wbstatus.state = WaterbowlState.FILTERING
      elif WaterbowlState.FILTERING == wbstatus.state:
        hw.setSterilizer(True)
        hw.setCirculatorPump(True)
        delayWithStatus(hw, wbstatus, "\033[31mFILTERING\033[0m", 60 * 10, 10)
        hw.setCirculatorPump(False)
        hw.setSterilizer(False)
        wbstatus.state = WaterbowlState.WAITING
      elif WaterbowlState.WAITING == wbstatus.state:
        hw.setSterilizer(False)
        hw.setCirculatorPump(False)
        hw.setInletValve(False)
        delayWithStatus(hw, wbstatus, "\033[32mWAITING\033[0m", 60 * 240, 10)
        hw.setCirculatorPump(False)
        hw.setSterilizer(False)
        wbstatus.state = WaterbowlState.WAITING
      else:
        wbstatus.state = WaterbowlState.IDLE
        
  #    delayWithStatus("\033[33mSETTLING\033[0m", 60 * 1, 10)
  except KeyboardInterrupt:
    hw.close()
    app.stop()
    print "Exiting cleanly"

  except:
    print "Unexpected exception"
    hw.close()
    app.stop()
    raise

  
  
if __name__== "__main__":
  main()

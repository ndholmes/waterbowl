# System imports
import sys
import time
import thread as thread
import datetime
import paho.mqtt.client as mqtt
import WaterbowlHardware
import pytz
import json

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
    output += '} }';
    return output

def delayWithStatus(hw, wbstatus, statusString, delayTimeSeconds, interval):
  timestamp = time.strftime("%d-%b-%Y %H:%M:%S")
  print("%s [%s] Delaying %d seconds, reporting every %d seconds" % (timestamp, statusString, delayTimeSeconds, interval))
  while delayTimeSeconds >= 0:
    timestamp = time.strftime("%d-%b-%Y %H:%M:%S")
    print("%s [%s] %ds remaining, Food: %d%% Tank: %d%% Temp: %.1fF" % (timestamp, statusString, delayTimeSeconds, wbstatus.foodLevel, wbstatus.tankLevel, wbstatus.airTempF))
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
    

print("wbstatus = %d" % (id(WaterbowlHardware.wbstatus)))

def mqtt_onConnect(client, userdata, flags, rc):
   if rc == 0:
      # Successful Connection
      print("Successful MQTT Connection")
      client.connected_flag = True
   elif rc == 1:
      print("ERROR: MQTT Incorrect Protocol Version")
      client.connected_flag = False
   elif rc == 2:
      print("ERROR: MQTT Invalid Client ID")
      client.connected_flag = False
   elif rc == 3:
      print("ERROR: MQTT Broker Unavailable")
      client.connected_flag = False
   elif rc == 4:
      print("ERROR: MQTT Bad Username/Password")
      client.connected_flag = False
   elif rc == 5:
      print("ERROR: MQTT Not Authorized")
      client.connected_flag = False
   else:
      print("ERROR: MQTT Other Failure %d" % (rc))
      client.connected_flag = False

def mqtt_onDisconnect(client, userdata, rc):
   print("MQTT disconnected - reason: [%s]" % (str(rc)))
   client.connected_flag = False

class GlobalConfiguration:
   sensors = None
   configOpts = None

   def __init__(self):
      self.sensors = { }
      self.configOpts = { }



def mqttSendSensor(mqttClient, gConf, sensor, value, units):
  try:
    topic = "%s/%s" % (gConf.configOpts['mqttPath'], sensor)
    updateMessage = {
       'type':'update',
       'value':value,
       'units': units,
       'time':datetime.datetime.utcnow().replace(tzinfo=pytz.utc).isoformat(),
       'source':gConf.configOpts['sourceName']
    }
    message = json.dumps(updateMessage, sort_keys=True)
    mqttClient.publish(topic=topic, payload=message)
    return True
  except Exception as e:
    print(e)
    return False

def mqttUpdateThread(mqttClient, gConf, wbstatus):
  lastMQTTConnectAttempt = 0
  lastUpdateTime = 0

  while True:
      if mqttClient.connected_flag is False and (lastMQTTConnectAttempt is None or lastMQTTConnectAttempt + gConf.configOpts['mqttReconnectInterval'] < time.time()):
        # We don't have an MQTT client and need to try reconnecting
        try:
          lastMQTTConnectAttempt = time.time()
          mqttClient.loop_start()
          mqttClient.connect(gConf.configOpts['mqttBroker'], gConf.configOpts['mqttPort'], keepalive=60)
          while not mqttClient.connected_flag: 
            time.sleep(2) # Wait for callback to fire
        except(KeyboardInterrupt):
          raise
        except:
          mqttClient.connected_flag = False

      if mqttClient.connected_flag is True and gConf.configOpts['mqttUpdateInterval'] > 0 and lastUpdateTime + gConf.configOpts['mqttUpdateInterval'] < time.time():
        print("Sending mqtt sensor update, next in %d seconds" % (gConf.configOpts['mqttUpdateInterval']))
        lastUpdateTime = time.time()        
        mqttSendSensor(mqttClient, gConf, "reservoirLevel", "%d" % (wbstatus.tankLevel), "percent")
        mqttSendSensor(mqttClient, gConf, "waterBowlLevel", "%d" % (wbstatus.bowlLevel), "percent")
        mqttSendSensor(mqttClient, gConf, "foodBowlLevel", "%d" % (wbstatus.foodLevel), "percent")
        mqttSendSensor(mqttClient, gConf, "temperature", "%.1f" % ((wbstatus.airTempF-32.0) * 5 / 9), "C")
        mqttSendSensor(mqttClient, gConf, "humidity", "%d" % (wbstatus.airHumidity), "percent")
        mqttSendSensor(mqttClient, gConf, "barometricPressure", "%.1f" % (wbstatus.airPressure), "hPa")
        mqttSendSensor(mqttClient, gConf, "state", ['IDLE','FILTERING','SETTLING','REFILLING','WAITING'][wbstatus.state], "string")

      time.sleep(1)


def main():
  wbstatus = WaterbowlHardware.wbstatus
  gConf = GlobalConfiguration()
  app = web.application(urls, globals())
  thread.start_new_thread(app.run, ())
  hw = WaterbowlHardware.WaterbowlHardware()
  hw.sensorInit()

  mqtt.Client.connected_flag = False
  mqttClient = mqtt.Client()
  mqttClient.on_connect=mqtt_onConnect
  mqttClient.on_disconnect=mqtt_onDisconnect
  
  gConf.configOpts['mqttUsername'] = None
  gConf.configOpts['mqttPassword'] = None
  gConf.configOpts['mqttBroker'] = 'copernicus.drgw.net'
  gConf.configOpts['mqttPort'] = 1883
  gConf.configOpts['mqttReconnectInterval'] = 30
  gConf.configOpts['mqttUpdateInterval'] = 60
  gConf.configOpts['mqttPath'] = 'house/waterbowl'
  gConf.configOpts['sourceName'] = 'waterbowl'
  if gConf.configOpts['mqttUsername'] is not None and gConf.configOpts['mqttPassword'] is not None:
    mqttClient.username_pw_set(username=gConf.configOpts['mqttUsername'], password=gConf.configOpts['mqttPassword'])

  thread.start_new_thread(mqttUpdateThread, (mqttClient, gConf, wbstatus))

  
  print("wbstatus = %d" % (id(wbstatus)))

  while True:
    try:


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
        wbstatus.state = WaterbowlState.REFILLING
      else:
        wbstatus.state = WaterbowlState.IDLE


  #    delayWithStatus("\033[33mSETTLING\033[0m", 60 * 1, 10)
    except KeyboardInterrupt:

      hw.close()
      app.stop()

      print("Exiting cleanly")
      raise

    except:
      print("Unexpected exception")
      mqttClient.loop_stop()
      hw.close()
      app.stop()
      raise

  
  
if __name__== "__main__":
  main()

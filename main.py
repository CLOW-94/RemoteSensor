import network
import time
from umqtt.simple import MQTTClient
from machine import Pin, I2C
import BMP280
from veml7700 import VEML7700

import config
import ota_update


# -----------------------------
# I2C sensor setup
# -----------------------------

i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=100000)

print("I2C devices:", [hex(addr) for addr in i2c.scan()])

bmp = BMP280.BMP280(i2c=i2c, address=0x76)
sensor = VEML7700(i2c)


# -----------------------------
# WiFi connection
# -----------------------------

def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(
            config.wifi_ssid,
            config.wifi_password
        )

        timeout = 20

        while not wlan.isconnected() and timeout > 0:
            print("Waiting for WiFi...")
            time.sleep(1)
            timeout -= 1

        if not wlan.isconnected():
            raise RuntimeError("WiFi connection failed")

    print("WiFi connected:", wlan.ifconfig()[0])
    return wlan


# -----------------------------
# MQTT connection
# -----------------------------

def mqtt_connect():
    client = MQTTClient(
        client_id=config.mqtt_client_id,
        server=config.mqtt_host,
        user=config.mqtt_username,
        password=config.mqtt_password
    )

    client.connect()
    print("MQTT connected")
    return client


# -----------------------------
# Connect WiFi
# -----------------------------

wlan = wifi_connect()


# -----------------------------
# OTA update check
# -----------------------------

print("Checking for OTA update...")
ota_update.check_for_updates()


# -----------------------------
# Connect MQTT
# -----------------------------

mqtt = mqtt_connect()


# -----------------------------
# Main loop
# -----------------------------

while True:

    try:

        if not wlan.isconnected():

            print("WiFi lost. Reconnecting...")

            wlan = wifi_connect()

            try:
                mqtt.disconnect()
            except:
                pass

            mqtt = mqtt_connect()

        temp_f = (bmp.read_temperature() / 100) * 9 / 5 + 32
        pressure = bmp.pressure
        lux = sensor.lux()

        temp_f_str = "{:.2f}".format(temp_f)
        pressure_str = str(pressure)
        lux_str = "{:.2f}".format(lux)

        mqtt.publish(config.temp_topic, temp_f_str)
        mqtt.publish(config.pressure_topic, pressure_str)
        mqtt.publish(config.light_topic, lux_str)

        print("Lux:", lux_str)
        print("Temperature F:", temp_f_str)
        print("Pressure:", pressure_str)
        print("Published OK")
        print("-----")

    except Exception as e:

        print("Publish error:", e)

        try:
            mqtt.disconnect()
        except:
            pass

        time.sleep(3)

        try:
            wlan = wifi_connect()
            mqtt = mqtt_connect()
        except Exception as reconnect_error:
            print("Reconnect failed:", reconnect_error)

    time.sleep(10)

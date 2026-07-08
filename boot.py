# main.py

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
        wlan.connect(config.wifi_ssid, config.wifi_password)

        while not wlan.isconnected():
            print("Waiting for WiFi...")
            time.sleep(1)

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
# Start WiFi
# -----------------------------

wlan = wifi_connect()


# -----------------------------
# OTA update check
# -----------------------------
# This checks GitHub once every boot.
# If update is found, it downloads files and reboots.

ota_update.check_for_updates()


# -----------------------------
# Start MQTT after OTA check
# -----------------------------

mqtt = mqtt_connect()


# -----------------------------
# Main loop
# -----------------------------

while True:
    try:
        if not wlan.isconnected():
            wlan = wifi_connect()
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

        print("Lux: {:.2f}".format(lux))
        print("Temperature F:", temp_f_str)
        print("Pressure:", pressure_str)
        print("Published OK")
        print("-----")

        # Optional debug prints:
        # print("Raw temp C x100:", bmp.read_temperature())
        # print("I2C scan:", [hex(addr) for addr in i2c.scan()])

    except Exception as e:
        print("Publish error:", e)

        try:
            mqtt.disconnect()
        except:
            pass

        time.sleep(3)
        mqtt = mqtt_connect()

    time.sleep(10)
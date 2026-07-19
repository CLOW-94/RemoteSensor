# ============================================================
# main.py
#
# This program:
# 1. Connects the ESP32/Pico W to WiFi
# 2. Checks for OTA updates
# 3. Connects to the MQTT broker running on your Raspberry Pi
# 4. Reads data from the BMP280 and VEML7700 sensors
# 5. Publishes one JSON payload to the MQTT topic:
#
#       office/telemetry
#
# Node-RED receives that MQTT message, writes it to InfluxDB,
# and Grafana displays it on your dashboard.
# ============================================================


# -----------------------------
# Import required libraries
# -----------------------------

# network is used to connect to WiFi
import network

# time is used for delays and loop timing
import time

# ujson converts Python dictionaries into JSON strings
# Example:
# {"temperature": 72.5}
import ujson

# MQTTClient is used to publish MQTT messages to Mosquitto
from umqtt.simple import MQTTClient

# Pin and I2C are used to communicate with the sensors
from machine import Pin, I2C

# BMP280 sensor library
# Used for temperature and pressure
import BMP280

# VEML7700 sensor library
# Used for light/lux readings
from veml7700 import VEML7700

# Local config file with WiFi and MQTT settings
import config

# Local OTA update module
import ota_update


# -----------------------------
# I2C sensor setup
# -----------------------------

# Create the I2C bus.
#
# Your current wiring uses:
# SCL = Pin 9
# SDA = Pin 8
#
# freq=100000 sets I2C speed to 100 kHz, which is safe for most sensors.
i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=100000)

# Scan the I2C bus and print detected device addresses.
# This is useful for troubleshooting wiring or sensor issues.
print("I2C devices:", [hex(addr) for addr in i2c.scan()])

# Create the BMP280 object.
# Your BMP280 is currently detected at address 0x76.
bmp = BMP280.BMP280(i2c=i2c, address=0x76)

# Create the VEML7700 light sensor object.
light_sensor = VEML7700(i2c)


# -----------------------------
# WiFi connection function
# -----------------------------


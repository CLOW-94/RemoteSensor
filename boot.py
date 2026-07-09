# main.py

import network
import time
import ujson
from umqtt.simple import MQTTClient
from machine import Pin, I2C
import BMP280
from veml7700 import VEML7700

import config
import ota_update


# -----------------------------
# I2C sensor setup
# -----------------------------

i2c = I2C(0, scl=Pin(4), sda=Pin(5), freq=100000)

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
# MQTT connection for ThingsBoard
# -----------------------------

def mqtt_connect():
    print("Connecting MQTT...")
    print("Host:", config.mqtt_host)
    print("Port:", config.mqtt_port)
    print("Client ID:", config.mqtt_client_id)
    print("Token first chars:", config.mqtt_token[:5] + "...")

    import socket

    try:
        addr = socket.getaddrinfo(config.mqtt_host, config.mqtt_port)[0][-1]
        print("MQTT socket address:", addr)

        test_socket = socket.socket()
        test_socket.settimeout(5)
        test_socket.connect(addr)
        print("Raw socket connection OK")
        test_socket.close()

    except Exception as socket_error:
        print("Raw socket connection failed:", socket_error)
        raise socket_error

    client = MQTTClient(
        client_id=config.mqtt_client_id.encode(),
        server=config.mqtt_host,
        port=config.mqtt_port,
        user=config.mqtt_token.encode(),
        password=b"",
        keepalive=60
    )

    client.connect()
    print("MQTT connected to ThingsBoard")
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
        # Reconnect WiFi/MQTT if WiFi drops
        if not wlan.isconnected():
            print("WiFi disconnected. Reconnecting...")
            wlan = wifi_connect()
            mqtt = mqtt_connect()

        # Read sensors
        temp_f = (bmp.read_temperature() / 100) * 9 / 5 + 32
        pressure = float(str(bmp.pressure).replace("hPa", "").strip())
        lux = sensor.lux()


        # Round values
        temp_f = round(temp_f, 2)
        pressure = round(pressure, 2)
        lux = round(lux, 2)


        # ThingsBoard expects JSON telemetry
        payload = {
            "temperature": temp_f,
            "pressure": pressure,
            "light": lux
        }

        payload_json = ujson.dumps(payload)

        # Publish all values to ThingsBoard telemetry topic
        mqtt.publish(config.telemetry_topic, payload_json)

        print("Published to ThingsBoard:")
        print(payload_json)
        print("-----")

        # Optional debug prints:
        # print("Raw temp C x100:", bmp.read_temperature())
        # print("I2C scan:", [hex(addr) for addr in i2c.scan()])
        # print("Lux:", lux)
        # print("Temperature F:", temp_f)
        # print("Pressure:", pressure)

    except Exception as e:
        print("Publish error:", e)

        try:
            mqtt.disconnect()
        except:
            pass

        time.sleep(3)

        try:
            mqtt = mqtt_connect()
        except Exception as reconnect_error:
            print("MQTT reconnect error:", reconnect_error)

    time.sleep(2)

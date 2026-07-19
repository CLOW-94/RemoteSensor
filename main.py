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
i2c = I2C(0, scl=Pin(4), sda=Pin(5), freq=100000)

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

def wifi_connect():
    """
    Connects the board to WiFi.

    Returns:
        wlan object if connected successfully

    Raises:
        RuntimeError if WiFi connection fails
    """

    # Create a station interface.
    # STA_IF means the board connects to an existing WiFi network.
    wlan = network.WLAN(network.STA_IF)

    # Turn on the WiFi interface.
    wlan.active(True)

    # If already connected, do not reconnect.
    if wlan.isconnected():
        print("WiFi already connected:", wlan.ifconfig()[0])
        return wlan

    # Start connecting to WiFi using credentials from config.py.
    print("Connecting to WiFi...")
    wlan.connect(config.wifi_ssid, config.wifi_password)

    # Wait up to 20 seconds for WiFi to connect.
    timeout = 20

    while not wlan.isconnected() and timeout > 0:
        print("Waiting for WiFi...")
        time.sleep(1)
        timeout -= 1

    # If WiFi still is not connected after timeout, stop with an error.
    if not wlan.isconnected():
        raise RuntimeError("WiFi connection failed")

    # Print the IP address assigned by your router.
    print("WiFi connected:", wlan.ifconfig()[0])

    return wlan


# -----------------------------
# MQTT connection function
# -----------------------------

def mqtt_connect():
    """
    Connects to the Mosquitto MQTT broker running on the Raspberry Pi.

    Returns:
        MQTTClient object if connected successfully
    """

    print("Connecting to MQTT broker:", config.mqtt_host)

    # If no MQTT username/password is set, connect anonymously.
    # This matches your current Mosquitto setup.
    if config.mqtt_username is None or config.mqtt_password is None:
        client = MQTTClient(
            client_id=config.mqtt_client_id,
            server=config.mqtt_host,
            port=config.mqtt_port
        )

    # If username/password are set later, use them.
    else:
        client = MQTTClient(
            client_id=config.mqtt_client_id,
            server=config.mqtt_host,
            port=config.mqtt_port,
            user=config.mqtt_username,
            password=config.mqtt_password
        )

    # Connect to Mosquitto.
    client.connect()

    print("MQTT connected")

    return client


def clean_number(value):
    """
    Converts a sensor value into a float.

    This handles:
    - normal numbers: 72.5
    - numeric strings: "72.5"
    - strings with units: "1013.25 hPa"
    - strings with labels: "Lux: 850.2"

    It extracts the first valid number it finds.
    """

    # Convert the value to a string
    text = str(value).strip()

    # This will hold the number characters we find
    number_text = ""

    # Track whether we have started reading a number
    started = False

    # Track whether we already used a decimal point
    decimal_used = False

    # Go through each character in the string
    for char in text:

        # Allow digits
        if char >= "0" and char <= "9":
            number_text += char
            started = True

        # Allow one decimal point after the number starts
        elif char == "." and started and not decimal_used:
            number_text += char
            decimal_used = True

        # Allow a minus sign only before the number starts
        elif char == "-" and not started:
            number_text += char
            started = True

        # If we already started reading a number and now hit
        # something else, stop reading
        elif started:
            break

    # If no number was found, raise a clear error
    if number_text == "" or number_text == "-":
        raise ValueError("No valid number found in value: {}".format(text))

    # Convert the cleaned number string to a float
    return float(number_text)

# -----------------------------
# Sensor reading function
# -----------------------------

# -----------------------------
# Sensor reading function
# -----------------------------

def read_sensors():
    """
    Reads all sensors and returns a dictionary ready to publish as JSON.

    This version safely cleans all sensor values before converting them
    to numbers. This helps if the sensor library returns a value as text
    instead of a normal int or float.
    """

    # Read raw temperature from the BMP280.
    # This library appears to return temperature multiplied by 100.
    # Example:
    # 2350 means 23.50 C
    temp_raw = bmp.read_temperature()

    # Read raw pressure from BMP280.
    # Depending on the BMP280 library, this may be returned as:
    # - an int
    # - a float
    # - a string
    # - a string with units
    pressure_raw = bmp.pressure

    # Read raw light level from VEML7700.
    # This may be returned as a float or string depending on the library.
    lux_raw = light_sensor.lux()

    # Print raw sensor values for troubleshooting.
    # Once everything is working, you can comment these out.
    print("Raw temperature:", temp_raw, "Type:", type(temp_raw))
    print("Raw pressure:", pressure_raw, "Type:", type(pressure_raw))
    print("Raw lux:", lux_raw, "Type:", type(lux_raw))

    # Clean and convert temperature.
    # Divide by 100 because your original working code did that.
    temp_c = clean_number(temp_raw) / 100

    # Convert Celsius to Fahrenheit.
    temp_f = temp_c * 9 / 5 + 32

    # Clean and convert pressure.
    pressure = clean_number(pressure_raw)

    # Clean and convert lux.
    lux = clean_number(lux_raw)

    # Build the JSON payload that will be sent to MQTT.
    # These names must match what your Node-RED flow expects.
    payload = {
        "temperature": round(temp_f, 2),
        "pressure": round(pressure, 2),
        "light": round(lux, 2)
    }

    return payload

# -----------------------------
# MQTT publish function
# -----------------------------

def publish_telemetry(client, payload):
    """
    Publishes the sensor payload to MQTT as a JSON string.

    Args:
        client: connected MQTTClient object
        payload: dictionary containing sensor data
    """

    # Convert the Python dictionary into a JSON string.
    #
    # Example:
    # {"temperature":72.4,"pressure":1013.2,"light":847.5}
    message = ujson.dumps(payload)

    # Publish the JSON message to the MQTT topic from config.py.
    #
    # Your Node-RED flow listens to:
    # office/telemetry
    client.publish(
        config.mqtt_telemetry_topic,
        message
    )

    # Print helpful debug information in the serial console.
    print("Published to:", config.mqtt_telemetry_topic)
    print("Payload:", message)


# -----------------------------
# Startup
# -----------------------------

# Connect to WiFi before doing anything that requires network access.
wlan = wifi_connect()


# -----------------------------
# OTA update check
# -----------------------------

# Check for OTA updates.
#
# This is wrapped in try/except so the sensor can still run even if
# the update check fails because of GitHub, WiFi, DNS, etc.
try:
    print("Checking for OTA update...")
    ota_update.check_for_updates()

except Exception as e:
    print("OTA update check failed:", e)


# -----------------------------
# MQTT startup
# -----------------------------

# Connect to the Raspberry Pi Mosquitto broker.
mqtt = mqtt_connect()


# -----------------------------
# Main loop
# -----------------------------

while True:

    try:
        # Check if WiFi is still connected.
        # If WiFi drops, reconnect WiFi and MQTT.
        if not wlan.isconnected():
            print("WiFi lost. Reconnecting...")

            # Try to disconnect MQTT cleanly.
            # If it fails, ignore the error because we are reconnecting anyway.
            try:
                mqtt.disconnect()
            except Exception:
                pass

            # Reconnect WiFi.
            wlan = wifi_connect()

            # Reconnect MQTT after WiFi is restored.
            mqtt = mqtt_connect()

        # Read the sensor values.
        payload = read_sensors()

        # Publish the sensor values to MQTT as JSON.
        publish_telemetry(mqtt, payload)

        print("-----")

    except Exception as e:
        # If anything goes wrong during reading or publishing,
        # print the error and try to reconnect.
        print("Publish error:", e)

        # Try to disconnect from MQTT before reconnecting.
        try:
            mqtt.disconnect()
        except Exception:
            pass

        # Wait briefly before reconnecting.
        time.sleep(3)

        # Try to recover WiFi and MQTT.
        try:
            wlan = wifi_connect()
            mqtt = mqtt_connect()

        except Exception as reconnect_error:
            print("Reconnect failed:", reconnect_error)

    # Wait before sending the next reading.
    time.sleep(config.publish_interval)

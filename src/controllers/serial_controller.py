import serial
import serial.tools.list_ports
import threading
import time
import pythoncom
from tkinter.messagebox import showerror
import sys
from collections import deque


class FastCascadedFilter:
    """Optimized cascaded filter for speed-critical applications."""
    def __init__(self):
        self.filter1 = AdaptiveEMA()
        self.filter2 = MedianFilter(window_size=5)

    def filter(self, new_value):
        filtered1 = self.filter1.filter(new_value)
        return self.filter2.filter(filtered1)


class AdaptiveEMA:
    def __init__(self, min_alpha=0.05, max_alpha=0.3, threshold=2.0):
        self.min_alpha = min_alpha
        self.max_alpha = max_alpha
        self.threshold = threshold
        self.value = None
        self.last_change = 0

    def filter(self, new_value):
        if self.value is None:
            self.value = new_value
            return self.value

        change = abs(new_value - self.value)
        self.last_change = change

        if change > self.threshold:
            alpha = self.max_alpha
        else:
            alpha = self.min_alpha + (self.max_alpha - self.min_alpha) * (change / self.threshold)

        self.value = alpha * new_value + (1 - alpha) * self.value
        return self.value


class MedianFilter:
    def __init__(self, window_size=3):
        self.window_size = window_size
        self.buffer = deque(maxlen=window_size)

    def filter(self, new_value):
        self.buffer.append(new_value)
        if len(self.buffer) < self.window_size:
            return new_value

        if self.window_size == 3:
            values = list(self.buffer)
            return sorted(values)[1]
        return new_value


class SerialController:
    def __init__(self, volume_callback, button_callback, connection_status_callback=None):
        """Initialize serial controller."""
        self.volume_callback = volume_callback
        self.button_callback = button_callback
        self.connection_status_callback = connection_status_callback
        self.button_state = None
        self.running = True
        self.arduino = None
        self.data_split = None
        self.device_name = "USB-SERIAL CH340", "Dispositivo de Série USB"
        self.is_connected = False

        self.volume_filters = [FastCascadedFilter() for _ in range(7)]

        self.initialize_serial()
        self.start_serial_thread()

    def get_com_port_by_device_name(self, device_name):
        """Returns the COM port number associated with the given device name."""
        ports = serial.tools.list_ports.comports()

        for port in ports:
            if device_name.lower() in port.description.lower():
                return port.device

        return None

    def initialize_serial(self, device_name="USB-SERIAL CH340", baud_rate=9600):
        """Initialize serial connection with the device."""
        serial_port = self.get_com_port_by_device_name(device_name)
        if serial_port:
            try:
                self.arduino = serial.Serial(serial_port, baud_rate)
                self.is_connected = True
                if self.connection_status_callback:
                    self.connection_status_callback(True)
                return self.arduino
            except Exception as e:
                print(f"Could not connect to the Mixer. Mixer already in use: {e}")
                self.is_connected = False
                if self.connection_status_callback:
                    self.connection_status_callback(False)
                return None
        else:
            print("Mixer not found. Check your connection.")
            self.is_connected = False
            if self.connection_status_callback:
                self.connection_status_callback(False)
            return None

    def reconnect_serial(self, device_name="USB-SERIAL CH340", baud_rate=9600):
        """Reconnect to the mixer."""
        if self.arduino:
            try:
                self.arduino.close()
            except:
                pass
        serial_port = self.get_com_port_by_device_name(device_name)
        if serial_port:
            try:
                self.arduino = serial.Serial(serial_port, baud_rate)
                self.is_connected = True
                if self.connection_status_callback:
                    self.connection_status_callback(True)
                return self.arduino
            except serial.SerialException as e:
                print(f"Serial exception during reconnect: {e}")
                self.is_connected = False
                if self.connection_status_callback:
                    self.connection_status_callback(False)
                time.sleep(1)
                return self.reconnect_serial()
        else:
            print("Serial port not found. Retrying...")
            self.is_connected = False
            if self.connection_status_callback:
                self.connection_status_callback(False)
            time.sleep(1)
            return self.reconnect_serial()

    def start_serial_thread(self):
        """Start serial communication thread."""
        thread = threading.Thread(target=self.read_serial_data, daemon=True)
        thread.start()

    def read_serial_data(self):
        """Process serial data from the device."""
        pythoncom.CoInitialize()

        while self.running:
            time.sleep(0.01)
            try:
                if self.arduino and self.arduino.in_waiting > 0:
                    data = self.arduino.readline().decode("utf-8").strip()
                    data_split = data.split("-")
                    self.process_volume_data(data_split[0])
                    self.process_button_data(data_split[1])
                else:
                    if self.arduino is None:
                        time.sleep(1)
                        self.initialize_serial()
            except serial.SerialException as e:
                print(f"Serial exception: {e}")
                self.is_connected = False
                if self.connection_status_callback:
                    self.connection_status_callback(False)
                time.sleep(1)
                self.reconnect_serial()
            except Exception as e:
                print(f"Exception occurred: {e}")
                continue

    def process_volume_data(self, data):
        """Process volume data received from serial."""
        volumes = data.split("|")

        smoothed_volumes = []
        for i, v in enumerate(volumes):
            try:
                value = float(v)
            except ValueError:
                value = 0
            if i < len(self.volume_filters):
                ema_smoothed = self.volume_filters[i].filter(value)
            else:
                ema_smoothed = value
            smoothed_volumes.append(int(round(ema_smoothed)))
        self.volume_callback(smoothed_volumes)

    def process_button_data(self, data):
        buttons = data.split("|")
        self.button_callback(buttons)

    def get_connection_status(self):
        """Get current connection status."""
        return self.is_connected

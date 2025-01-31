import serial
import serial.tools.list_ports
import threading
import time
import pythoncom
from tkinter.messagebox import showerror
import sys

class SerialController:
    def __init__(self, volume_callback):
        """
        Initialize serial controller
        volume_callback: function that receives volume data updates
        """
        self.volume_callback = volume_callback
        self.running = True
        self.arduino = None
        self.initialize_serial()
        self.start_serial_thread()

    def get_com_port_by_device_name(self, device_name):
        """
        Returns the COM port number associated with the given device name.
        """
        ports = serial.tools.list_ports.comports()  # Get all available COM ports

        for port in ports:
            if device_name.lower() in port.description.lower():  # Check if the device name matches
                return port.device  # Return the COM port (e.g., 'COM3')

        return None  # Return None if no matching device is found

    def initialize_serial(self, device_name="USB-SERIAL CH340", baud_rate=9600):
        """
        Initialize serial connection with the device
        """
        serial_port = self.get_com_port_by_device_name(device_name)
        if serial_port:
            try:
                self.arduino = serial.Serial(serial_port, baud_rate)
                return self.arduino
            except Exception as e:
                showerror('Error', f"Could not connect to the Mixer: {e}")
                self.initialize_serial()
        else:
            showerror('Error', 'Mixer not found. Check your connection.')
            self.initialize_serial()

    def reconnect_serial(self, device_name="USB-SERIAL CH340", baud_rate=9600):
        """Reconnect to the mixer"""
        serial_port = self.get_com_port_by_device_name(device_name)
        if serial_port:
            try:
                self.arduino = serial.Serial(serial_port, baud_rate)
                return self.arduino
            except Exception as e:
                self.reconnect_serial()
        else:
            self.reconnect_serial()

    def start_serial_thread(self):
        """Start serial communication thread"""
        thread = threading.Thread(target=self.read_serial_data, daemon=True)
        thread.start()

    def read_serial_data(self):
        """Process serial data from the device"""
        pythoncom.CoInitialize()
        
        while self.running:
            time.sleep(0.01)
            try:
                if self.arduino and self.arduino.in_waiting > 0:
                    data = self.arduino.readline().decode('utf-8').strip()
                    self.process_volume_data(data)
                else:
                    # If Arduino is not connected, we can try to read to check
                    if self.arduino is None:
                        time.sleep(1)
                        self.initialize_serial()  # Attempt to reconnect
            except serial.SerialException as e:
                # Handle the case where the Arduino is disconnected
                time.sleep(1)
                self.reconnect_serial()  # Attempt to reconnect
            except Exception as e:
                print(f"Exception occurred: {e}")  # Debugging line
                continue
                    
    def process_volume_data(self, data):
        """Process volume data received from serial"""
        volumes = data.split('|')
        self.volume_callback(volumes)

    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if self.arduino:
            self.arduino.close()
#!/usr/bin/python
"""\
Simple g-code streaming server for Polargraph
"""
 
import serial
import time
import argparse
import math
import os
from gcodeparser import GcodeParser
from flask import Flask
import json
import threading

## Polargraph parameters
# Homing location
A_X_HOME_OFFSET = 456/2
A_Y_HOME_OFFSET = -540
B_X_HOME_OFFSET = -456/2
B_Y_HOME_OFFSET = -540
# Origin location (rel. to home)
X_ORIGIN_OFFSET = 0
Y_ORIGIN_OFFSET = 229
# Calc constants
A_HOME = math.sqrt(A_X_HOME_OFFSET**2+A_Y_HOME_OFFSET**2)
B_HOME = math.sqrt(B_X_HOME_OFFSET**2+B_Y_HOME_OFFSET**2)
# Commands to send when cancelling print
CANCEL_CMDS = ["M3 S500 G4 P0.1","G0 X0 Y-215","G0 X0","G0 Y0","G4 P0.1"]

## Server parameters
printer_port = "/dev/ttyACM0"
gcode_dir = "gcode"

def gcode_coord_transform(gcode_command):
	command = []
	for line in GcodeParser(gcode_command).lines:
		if 'X' in line.params and 'Y' in line.params and (line.command == ('G',0) or line.command == ('G',1)):
			x_coord = line.get_param('X')
			y_coord = line.get_param('Y')
			a_coord = math.sqrt((A_X_HOME_OFFSET+X_ORIGIN_OFFSET+x_coord)**2+(A_Y_HOME_OFFSET+Y_ORIGIN_OFFSET+y_coord)**2)
			b_coord = math.sqrt((B_X_HOME_OFFSET+X_ORIGIN_OFFSET+x_coord)**2+(B_Y_HOME_OFFSET+Y_ORIGIN_OFFSET+y_coord)**2)
			a_coord = round(a_coord-A_HOME, 3)
			b_coord = round(b_coord-B_HOME, 3)
			line.update_param('X', a_coord)
			line.update_param('Y', b_coord)
		command.append(line.gcode_str)
	
	return " ".join(command)

def removeComment(string):
	if (string.find(';')==-1):
		return string
	else:
		return string[:string.index(';')]

# Printer lock, lock before calling function below
printer_busy = threading.Lock()
status_print = {'status': 'idle',
				'file': ''}

def print_file(serialport, filename):
	global cancel_print
	global status_print
	
	cancel_print = False
	status_print['status'] = 'printing'
	
	## show values ##
	print("USB Port: %s" % serialport )
	print("Gcode file: %s" % filename )
	
	# Open serial port
	try:
		s = serial.Serial(serialport,115200)
		print('Opening Serial Port')
	except:
		print("Error opening serial port")
		printer_busy.release()
		status_print['status'] = 'idle'
		status_print['file'] = ''
		return
	 
	# Open g-code file
	f = open(filename,'r')
	print('Opening gcode file')
	 
	# Wake up 
	s.write(str.encode("\r\n\r\n")) # Hit enter a few times to wake grbl
	time.sleep(2)   # Wait for grbl to initialize
	s.flushInput()  # Flush startup text in serial input
	print('Sending gcode')
	 
	# Stream g-code
	for line in f:
		l = removeComment(line)
		l = l.strip() # Strip all EOL characters for streaming
		if  (l.isspace()==False and len(l)>0) :
			l = gcode_coord_transform(l)
			print ('Sending: ' + l)
			s.write(str.encode(l + '\n')) # Send g-code block
			grbl_out = s.readline() # Wait for response with carriage return
			print (' : ' + grbl_out.strip().decode('utf-8'))
		if cancel_print:
			status_print['status'] = 'cancelling'
			for cmd in CANCEL_CMDS:
				l = removeComment(cmd)
				l = l.strip() # Strip all EOL characters for streaming
				if  (l.isspace()==False and len(l)>0) :
					l = gcode_coord_transform(l)
					print ('Sending: ' + l)
					s.write(str.encode(l + '\n')) # Send g-code block
					grbl_out = s.readline() # Wait for response with carriage return
					print (' : ' + grbl_out.strip().decode('utf-8'))
			cancel_print = False
			break
	 
	# Close file and serial port
	f.close()
	s.close()
	
	# Release lock
	printer_busy.release()
	status_print['status'] = 'idle'
	status_print['file'] = ''
	
# Main code
app = Flask(__name__)

@app.route('/')
def root():
	return app.send_static_file('index.html')

@app.route("/print/<filename>")
def print_start(filename):
	global status_print
    
	path = os.path.join(gcode_dir, filename) + ".gcode"
	if os.path.exists(path):
		# Get lock
		if printer_busy.acquire(blocking=False):
			t = threading.Thread(target=print_file, args=(printer_port, path))
			t.start()
			status_print['file'] = filename
			response = {   "result" : "success",
					   "message" : f"found {filename}, started print" }
		else:
			response = {   "result" : "failure",
							"message" : f"found {filename}, printer busy" }
	else:
		response = {   "result" : "failure",
					   "message" : f"{filename} not found" }
	return json.dumps(response)

@app.route("/cancel")
def print_cancel():
	global cancel_print
	
	cancel_print = True
	response = {   "result" : "success",
					   "message" : "cancellation flag set" }
	return json.dumps(response)
	
@app.route("/status")
def print_status():
	global status_print
	
	return json.dumps(status_print)
	
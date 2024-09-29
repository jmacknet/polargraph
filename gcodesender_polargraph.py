#!/usr/bin/python
"""\
Simple g-code streaming script
"""
 
import serial
import time
import argparse
import math
from gcodeparser import GcodeParser

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

parser = argparse.ArgumentParser(description='This is a basic gcode sender. http://crcibernetica.com')
parser.add_argument('-p','--port',help='Input USB port',required=True)
parser.add_argument('-f','--file',help='Gcode file name',required=True)
args = parser.parse_args()
 
## show values ##
print("USB Port: %s" % args.port )
print("Gcode file: %s" % args.file )

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
 
# Open serial port
s = serial.Serial(args.port,115200)
print('Opening Serial Port')
 
# Open g-code file
f = open(args.file,'r')
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
 
# Wait here until printing is finished to close serial port and file.
input("  Press <Enter> to exit.")
 
# Close file and serial port
f.close()
s.close()
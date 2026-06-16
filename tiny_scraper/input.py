import struct
import os
import re

code = 0
codeName = ""
value = 0

mapping = {
	304: "A",
	305: "B",
	306: "Y",
	307: "X",
	308: "L1",
	309: "R1",
	314: "L2",
	315: "R2",
	17: "DY",
	16: "DX",
	310: "SELECT",
	311: "START",
	312: "MENUF",
	114: "V+",
	115: "V-",
}

def find_gamepad_device():
	"""找 Handlers 中包含 js 的手柄设备对应的 event 路径"""
	try:
		with open("/proc/bus/input/devices", "r") as f:
			content = f.read()
	except FileNotFoundError:
		return None

	for block in content.strip().split("\n\n"):
		handlers_match = re.search(r"H: Handlers=([^\n]+)", block)
		if handlers_match and "js" in handlers_match.group(1):
			event_match = re.search(r"\b(event\d+)\b", block)
			if event_match:
				path = f"/dev/input/{event_match.group(1)}"
				if os.path.exists(path):
					return path
	return None

def check():
	global type, code, codeName, codeDown, value, valueDown
	dev = find_gamepad_device()
	if not dev:
		return
	try:
		with open(dev, "rb") as f:
			while True:
				event = f.read(24)
				
				if event:
					(tv_sec, tv_usec, type, kcode, kvalue) = struct.unpack('llHHI', event)
					if kvalue != 0:
						if kvalue != 1:
							kvalue = -1
						code = kcode
						codeName = mapping.get(code, str(code))
						value = kvalue						
						return
	except FileNotFoundError:
		return

def key(keyCodeName, keyValue = 99):
	global code, codeName, value
	if codeName == keyCodeName:
		if keyValue != 99: 
			return value == keyValue
		return True

def reset_input():
	global codeName, value
	codeName = ""
	value = 0

# -*- coding: utf-8 -*-
import sys
import os
import re
import json
import time
import datetime

from cept import Cept
from user import User
from editor import Editor
from messaging import Messaging
from messaging import Messaging_UI

# paths
PATH_DATA = "data/"

user = None

# globals

last_filename_include = ""
last_filename_palette = ""
links = {}

def format_currency(price):
	return "DM  %d" % int(price / 100) + ",%02d" % int(price % 100)

def headerfooter(pageid, publisher_name, publisher_color):
	hide_header_footer = len(publisher_name) == 0
	hide_price = False
	# Early screenshots had a two-line publisher name with
	# the BTX logo in it for BTX-internal pages. Some .meta
	# files still reference this, but we should remove this.
	if publisher_name == "!BTX":
#		publisher_name = (
#			b'\x1b\x22\x41'                 # parallel mode
#			b'\x9b\x30\x40'                 # select palette #0
#			b'\x9e'                         # ???
#			b'\x87'                         # set fg color to #7
#			b'\x1b\x28\x20\x40'             # load DRCs into G0
#			b'\x0f'                         # G0 into left charset
#			b'\x21\x22\x23'                 # "!"#"
#			b'\n'
#			b'\r'
#			b'\x24\x25\x26'                 # "$%&"
#			b'\x0b'                         # cursor up
#			b'\x09'                         # cursor right
#			b'\x1b\x28\x40'                 # load G0 into G0
#			b'\x0f'                         # G0 into left charset
#			b'\n'
#			b'\x8d'                         # double height
#			# TODO: this does not draw!! :(
#			b'Bildschirmtext'
#		)
		publisher_name = "Bildschirmtext"
		hide_price = True
	else:
		publisher_name = publisher_name[:30]

	hf = bytearray(Cept.set_res_40_24())
	hf.extend(Cept.set_cursor(23, 1))
	hf.extend(Cept.unprotect_line())
	hf.extend(Cept.set_line_fg_color_simple(12))
	hf.extend(Cept.parallel_limited_mode())
	hf.extend(Cept.set_cursor(24, 1))
	hf.extend(Cept.unprotect_line())
	hf.extend(b' \b')
	hf.extend(Cept.clear_line())
	hf.extend(Cept.cursor_home())
	hf.extend(Cept.unprotect_line())
	hf.extend(b' \b')
	hf.extend(Cept.clear_line())
	hf.extend(Cept.serial_limited_mode())
	hf.extend(Cept.set_cursor(24, 1))
	hf.extend(Cept.set_fg_color(8))
	hf.extend(b'\b')
	hf.extend(Cept.code_9d())
	hf.extend(b'\b')

	if publisher_color < 8:
		color_string = Cept.set_fg_color(publisher_color)
	else:
		color_string = Cept.set_fg_color_simple(publisher_color - 8)

	hf.extend(color_string)

	hf.extend(Cept.set_cursor(24, 19))

	if not hide_header_footer:
		hf.extend(Cept.from_str(pageid).rjust(22))

	hf.extend(Cept.cursor_home())
	hf.extend(Cept.set_palette(1))
	hf.extend(Cept.set_fg_color(8))
	hf.extend(b'\b')
	hf.extend(Cept.code_9d())
	hf.extend(b'\b')
	
	hf.extend(color_string)

	hf.extend(b'\r')

	hf.extend(Cept.from_str(publisher_name))

	# TODO: price
	if not hide_header_footer and not hide_price:
		hf.extend(Cept.set_cursor(1, 31))
		hf.extend(b'  ')
		hf.extend(Cept.from_str(format_currency(0)))

	hf.extend(Cept.cursor_home())
	hf.extend(Cept.set_palette(0))
	hf.extend(Cept.protect_line())
	hf.extend(b'\n')
	return hf

def create_system_message(code, price = 0, hint = ""):
	text = ""
	prefix = "SH"
	if hint != "":
		text = hint
	elif code == 0:
		text = "                               "
	elif code == 10:
		text = "Rückblättern nicht möglich     "
	elif code == 44:
		text = "Absenden? Ja:19 Nein:2         "
	elif code == 47:
		text = "Absenden für " + format_currency(price) + "? Ja:19 Nein:2"
	elif code == 55:
		text = "Eingabe wird bearbeitet        "
	elif code == 73:
		current_datetime = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
		text = "Abgesandt " + current_datetime + ", -> #  "
		prefix = "1B"
	elif code == 100 or code == 101:
		text = "Seite nicht vorhanden          "
	elif code == 291:
		text = "Seite wird aufgebaut           "
	elif code == 998:
		text = "Ungültiger Teilnehmer oder Kennwort"

	msg = bytearray(Cept.service_break(24))
	msg.extend(Cept.clear_line())
	msg.extend(Cept.from_str(text, 1))
	msg.extend(Cept.hide_text())
	msg.extend(b'\b')
	msg.extend(Cept.from_str(prefix))
	msg.extend(Cept.from_str(str(code)).rjust(3, b'0'))
	msg.extend(Cept.service_break_back())
	return msg

def create_preamble(basedir, meta):
	global last_filename_include
	global last_filename_palette

	preamble = b''

	# define palette
	if "palette" in meta:
		palette = meta["palette"]
		filename_palette = basedir + meta["palette"] + ".pal"
		sys.stderr.write("filename_palette = " + filename_palette + "\n")
		sys.stderr.write("last_filename_palette = " + last_filename_palette + "\n")
		if filename_palette != last_filename_palette:
			last_filename_palette = filename_palette
			with open(filename_palette) as f:
				palette = json.load(f)
			palette_data = Cept.define_palette(palette["palette"])
			preamble += palette_data
		else:
			sys.stderr.write("skipping palette\n")
	else:
		last_filename_palette = ""

	if "include" in meta:
		filename_include = basedir + meta["include"] + ".inc"
		if filename_include != last_filename_include:
			last_filename_include = filename_include
			with open(filename_include, mode='rb') as f:
				data_include = f.read()
			# palette definition has to end with 0x1f; add one if
			# the include data doesn't start with one
			if data_include[0] != 0x1f:
				preamble += Cept.set_cursor(1, 1)
			preamble += data_include
	else:
		last_filename_include = ""

	if len(preamble) > 600: # > 4 seconds @ 1200 baud
		preamble = create_system_message(291) + preamble

	return preamble

def replace_placeholders(cept):
	global user

	current_date = datetime.datetime.now().strftime("%d.%m.%Y")
	current_time = datetime.datetime.now().strftime("%H:%M")

	while True:
		found = False
		# TODO: convert into lookup table
		pos = cept.find(b'\x1f\x40\x41')
		if pos > 0:
			cept = cept[:pos] + Cept.from_str(current_date) + cept[pos+3:]
			found = True
			pos = cept.find(b'\x1f\x40\x42')
		if pos > 0:
			cept = cept[:pos] + Cept.from_str(user.salutation) + cept[pos+3:]
			found = True
	
		pos = cept.find(b'\x1f\x40\x43')
		if pos > 0:
			cept = cept[:pos] + Cept.from_str(user.first_name) + cept[pos+3:]
			found = True
	
		pos = cept.find(b'\x1f\x40\x44')
		if pos > 0:
			cept = cept[:pos] + Cept.from_str(user.last_name) + cept[pos+3:]
			found = True
	
		pos = cept.find(b'\x1f\x40\x45')
		if pos > 0:
			if user.stats.last_login is not None:
				t = datetime.datetime.fromtimestamp(user.stats.last_login)
				cept = cept[:pos] + Cept.from_str(t.strftime("%d.%m.%Y")) + cept[pos+3:]
			else:
				cept = cept[:pos] + Cept.from_str("--.--.----") + cept[pos+3:]
			found = True
	
		pos = cept.find(b'\x1f\x40\x46')
		if pos > 0:
			if user.stats.last_login is not None:
				t = datetime.datetime.fromtimestamp(user.stats.last_login)
				cept = cept[:pos] + Cept.from_str(t.strftime("%H:%M")) + cept[pos+3:]
			else:
				cept = cept[:pos] + Cept.from_str("--:--") + cept[pos+3:]
			found = True
	
		pos = cept.find(b'\x1f\x40\x47')
		if pos > 0:
			cept = cept[:pos] + Cept.from_str(user.user_id) + cept[pos+3:]
			found = True
	
		pos = cept.find(b'\x1f\x40\x48')
		if pos > 0:
			cept = cept[:pos] + Cept.from_str(user.ext) + cept[pos+3:]
			found = True
	
		pos = cept.find(b'\x1f\x40\x49')
		if pos > 0:
			cept = cept[:pos] + Cept.from_str(current_time) + cept[pos+3:]
			found = True
				
		if not found:
			break

	return cept

def create_page(basepath, pageid):
	if pageid[-1:].isdigit():
		pageid += "a"

	basedir = None

	for i in reversed(range(0, len(pageid))):
		testdir = basepath + pageid[:i+1]
		if os.path.isdir(testdir):
			sys.stderr.write("testdir: '" + testdir + "'\n")
			filename = pageid[i+1:]
			sys.stderr.write("filename: '" + filename + "'\n")
			basedir = testdir + "/"
			break

	if basedir is None:
		return None

	# generated pages
	sys.stderr.write("pageid[0]: '" + pageid[0] + "'\n")
	if pageid[0] == '8':
		ret = Messaging_UI.messaging_create_page(user, pageid)
		if ret is None:
			return None
		(meta, data_cept) = ret
	else:
		filename_meta = basedir + filename + ".meta"
		filename_cept = basedir + filename + ".cept"

		if not os.path.isfile(filename_meta):
			return None

		with open(filename_meta) as f:
			meta = json.load(f)
		
		with open(filename_cept, mode='rb') as f:
			data_cept = f.read()
	
		data_cept = replace_placeholders(data_cept)

	with open(basedir + "a.glob") as f:
		glob = json.load(f)
	meta.update(glob) # combine dicts, glob overrides meta

	all_data = bytearray(Cept.hide_cursor())

	if "clear_screen" in meta and meta["clear_screen"]:
		all_data.extend(Cept.serial_limited_mode())
		all_data.extend(Cept.clear_screen())

	all_data.extend(create_preamble(basedir, meta))

	if "cls2" in meta and meta["cls2"]:
		all_data.extend(Cept.serial_limited_mode())
		all_data.extend(Cept.clear_screen())

	# header
	hf = headerfooter(pageid, meta["publisher_name"], meta["publisher_color"])
	all_data.extend(hf)

	# payload
	all_data.extend(data_cept)

	all_data.extend(Cept.serial_limited_mode())

	# footer
	all_data.extend(hf)

	all_data.extend(Cept.sequence_end_of_page())

	inputs = meta.get("inputs")
	return (all_data, meta["links"], inputs)


def login(input_data):
	global user
	
	user_id = input_data["user_id"]
	if user_id is None or user_id == "":
		user_id = "0"
	ext = input_data["ext"]
	if ext is None or ext == "":
		ext = "1"
	user = User.login(user_id, ext, input_data["password"])
	
	return not user is None

def handle_inputs(inputs):
	global user

	while True:
		cept_data = bytearray(Cept.parallel_limited_mode())

		editors = []

		for input in inputs["fields"]:
			editor = Editor()
			editor.line = input["line"]
			editor.column = input["column"]
			editor.height = input["height"]
			editor.width = input["width"]
			editor.fgcolor = input["fgcolor"]
			editor.bgcolor = input["bgcolor"]
			editors.append(editor)

		for editor in editors:
			editor.draw_background()

		i = 0
		input_data = {}
		for editor in editors:
			input = inputs["fields"][i]

			hint = input.get("hint", "")
			type = input.get("type")

			while True:
				cept_data = create_system_message(0, 0, hint)
				sys.stdout.buffer.write(cept_data)
				sys.stdout.flush()
	
				val = editor.edit()
				input_data[input["name"]] = val
				
				if type == "user_id":
					user_id = val
					if User.exists(user_id):
						break
					else:
						cept_data = create_system_message(0, 0, "Teilnehmerkennung ungültig!")
						sys.stdout.buffer.write(cept_data)
						sys.stdout.flush()
				elif type == "ext":
					if val == "":
						ext = "1"
					else:
						ext = val
					if User.exists(user_id, ext):
						break
					else:
						cept_data = create_system_message(0, 0, "Mutbenutzernummer ungültig!")
						sys.stdout.buffer.write(cept_data)
						sys.stdout.flush()
				else:
					break
			
			i += 1

		if not "confirm" in inputs or inputs["confirm"]:
			# "send?" message
			if "price" in inputs:
				price = inputs["price"]
				cept_data = bytearray(create_system_message(47, price))
			else:
				price = 0
				cept_data = bytearray(create_system_message(44))
			cept_data.extend(Cept.set_cursor(24, 1))
			cept_data.extend(Cept.sequence_end_of_page())
			sys.stdout.buffer.write(cept_data)
			sys.stdout.flush()
		
			seen_a_one = False
			while True:
				c = sys.stdin.read(1)
				if c == "2":
					doit = False
					sys.stdout.write(c)
					sys.stdout.flush()
					break
				elif c == "1" and not seen_a_one:
					seen_a_one = True
					sys.stdout.write(c)
					sys.stdout.flush()
				elif c == "9" and seen_a_one:
					doit = True
					sys.stdout.write(c)
					sys.stdout.flush()
					break
				elif ord(c) == 8 and seen_a_one:
					seen_a_one = False
					sys.stdout.buffer.write(b'\b \b')
					sys.stdout.flush()

			if doit and inputs.get("action") == "send_message":
				messaging = Messaging(user)
				messaging.send(input_data["user_id"], input_data["ext"], input_data["body"])

				# "sent" message
				cept_data = bytearray(create_system_message(73))
				cept_data.extend(Cept.set_cursor(24, 1))
				cept_data.extend(Cept.sequence_end_of_page())
				sys.stdout.buffer.write(cept_data)
				sys.stdout.flush()
				while True:
					c = sys.stdin.read(1)
					if ord(c) == Cept.ter():
						sys.stdout.write(c)
						sys.stdout.flush()
						break
		else:				
			cept_data = create_system_message(55)
			sys.stdout.buffer.write(cept_data)
			sys.stdout.flush()
	
		# login page
		if "is_login" in inputs and inputs["is_login"]:
			if not login(input_data):
				sys.stderr.write("login incorrect\n")
				cept_data = create_system_message(998)
				sys.stdout.buffer.write(cept_data)
				sys.stdout.flush()
				continue
			else:
				sys.stderr.write("login ok\n")
		#else:
			# send "input_data" to "inputs["target"]"
			
		cept_data = bytearray(create_system_message(0))
		cept_data.extend(Cept.sequence_end_of_page())
		sys.stdout.buffer.write(cept_data)
		sys.stdout.flush()
		
		if inputs["target"][:5] == "page:":
			return inputs["target"][5:]
		else:
			return ""


def show_page(pageid):
	global links
	
	while True:
		if user is not None:
			user.stats.update()

		sys.stderr.write("showing page: '" + pageid + "'\n")
		ret = create_page(PATH_DATA, pageid)

		if ret is None:
			return False

		(cept_data, links, inputs) = ret
		sys.stdout.buffer.write(cept_data)
		sys.stdout.flush()
		
		if inputs is None:
			return True

		desired_pageid = handle_inputs(inputs)
		if desired_pageid != "*00":
			pageid = desired_pageid

def wait_for_dial_command():
	s = ""
	while True:
		c = sys.stdin.read(1)
		sys.stdout.write(c)
		sys.stdout.flush()
		if ord(c) == 10 or ord(c) == 13:
			sys.stderr.write("Modem command: '" + s + "'\n")
			if re.search("^AT *(X\d)? *D.*", s):
				break
			s = ""
		else:
			s += c
#		sys.stderr.write("'")
#		for cc in s:
#			if ord(cc) == 10:
#				sys.stderr.write("\\r")
#			if ord(cc) == 13:
#				sys.stderr.write("\\n")
#			else:
#				sys.stderr.write(cc)
#		sys.stderr.write("'\n")

# MAIN

sys.stderr.write("Neu-Ulm running.\n")

# TODO: generalize "c64": command line option to wait for n CRs
# TODO: command line option to log in a user
# TODO: command line option to navigate to a specific page

for arg in sys.argv[1:]:
	if arg == "--modem":
		wait_for_dial_command()

current_pageid = None
history = []

desired_pageid = "00000" # login page
#desired_pageid = "0"

showing_message = False

while True:
	if desired_pageid == "00":
		# reload
		desired_pageid = history[-1]
		history = history[:-1]

	is_back = (desired_pageid == "")

	if is_back:
		if len(history) < 2:
			is_back = False
			sys.stderr.write("ERROR: No history.\n")
			sys.stdout.buffer.write(create_system_message(10) + Cept.sequence_end_of_page())
			sys.stdout.flush()
			showing_message = True
		else:
			desired_pageid = history[-2]
			history = history[:-2]

	if desired_pageid and show_page(desired_pageid):
		# showing page worked
		current_pageid = desired_pageid
		history.append(current_pageid)
	else:
		code = 100
		if desired_pageid:
			sys.stderr.write("ERROR: Page not found: " + desired_pageid + "\n")
			if (desired_pageid[-1] >= "b" and desired_pageid[-1] <= "z"):
				code = 101
		cept_data = create_system_message(code) + Cept.sequence_end_of_page()
		sys.stdout.buffer.write(cept_data)
		sys.stdout.flush()
		showing_message = True
		if is_back:
			# Going back failed -> we're still on the same page.
			# Re-add the current page, but the previous page is removed from history
			history.append(current_pageid)
		else:
			# showing page failed, current_pageid and history are unchanged
			pass
	
	desired_pageid = None
	
	allowed_inputs = list(links.keys())
	if "#" in allowed_inputs:
		allowed_inputs.remove("#")

	editor = Editor()
	editor.line = 24
	editor.column = 1
	editor.height = 1
	editor.width = 40
	editor.allowed_inputs = allowed_inputs
	val = editor.edit()

	if val and val[0] == chr(Cept.ini()):
		# global address
		desired_pageid = val[1:]
	elif val in links:
		# link
		desired_pageid = links[val]
	elif not val and links.get("#"):
		# #-link
		sys.stderr.write("Cept.ter")
		desired_pageid = links["#"]
	else:
		desired_pageid = None
		
	
	


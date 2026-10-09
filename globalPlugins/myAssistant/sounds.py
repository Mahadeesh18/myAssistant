# -*- coding: UTF-8 -*-
"""Sound effects: short generated WAV files played through NVDA's audio output."""
import json
import os
import globalVars
import addonHandler

addonHandler.initTranslation()

SOUND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sounds"))
CONFIG_FILE = os.path.join(globalVars.appArgs.configPath, "myAssistantSounds.json")
# Put your own enter.wav, exit.wav, move.wav (or any other sound name below) in this folder and they replace the built-in ones.
USER_DIR = os.path.join(globalVars.appArgs.configPath, "myAssistantSounds")

# (label shown in the list, file name without .wav)
SOUNDS = [
	(_("Menu opened (enter)"), "enter"),
	(_("Menu closed (exit)"), "exit"),
	(_("Moving through the menu"), "move"),
	(_("Dialog opened"), "open"),
	(_("Dialog closed"), "close"),
	(_("Working, please wait"), "working"),
	(_("Task finished successfully"), "success"),
	(_("Error"), "error"),
	(_("Notification"), "notify"),
	(_("Copied to clipboard"), "copy"),
	(_("Alarm"), "alarm"),
	(_("Long task started"), "sweep"),
]

_state = {"enabled": None}


def is_enabled():
	if _state["enabled"] is None:
		try:
			with open(CONFIG_FILE, "r", encoding="utf-8") as f:
				_state["enabled"] = bool(json.load(f).get("enabled", True))
		except Exception:
			_state["enabled"] = True
	return _state["enabled"]


def set_enabled(value):
	_state["enabled"] = bool(value)
	try:
		with open(CONFIG_FILE, "w", encoding="utf-8") as f:
			json.dump({"enabled": _state["enabled"]}, f)
	except Exception:
		pass


def _find(name):
	"""Your own file in the NVDA configuration folder wins over the one inside the add-on."""
	for folder in (USER_DIR, SOUND_DIR):
		path = os.path.join(folder, name + ".wav")
		if os.path.isfile(path):
			return path
	return None


def play(name, force=False):
	"""Play a sound effect without blocking. Never raises."""
	if not force and not is_enabled():
		return
	try:
		import nvwave
		path = _find(name)
		if path:
			nvwave.playWaveFile(path, asynchronous=True)
	except Exception:
		pass


ALARM_DIR = os.path.join(SOUND_DIR, "alarms")


def alarm_path(file_name):
	return os.path.join(ALARM_DIR, file_name + ".wav")


def play_path(path):
	"""Play any WAV file without blocking (used for alarm sounds, which ignore the sound effects switch)."""
	try:
		import nvwave
		if os.path.isfile(path):
			nvwave.playWaveFile(path, asynchronous=True)
	except Exception:
		pass

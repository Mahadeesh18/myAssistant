# -*- coding: UTF-8 -*-
"""AI: Gemini voices text to speech.

Enter your text, choose a voice, press Generate Audio. The audio plays, and the result box has a
Save Audio button that saves it as a WAV file.
"""
import base64
import json
import os
import re
import struct
import tempfile
import urllib.error
import urllib.request
import wx
import gui
import addonHandler
from gui import guiHelper
from . import providers, sounds
from .common import speak, bg, show_text, _finish, _modal

addonHandler.initTranslation()

# The 30 prebuilt Gemini voices (name, short description of the sound).
VOICES = [
	("Kore", "Firm"), ("Zephyr", "Bright"), ("Puck", "Upbeat"), ("Charon", "Informative"),
	("Fenrir", "Excitable"), ("Leda", "Youthful"), ("Orus", "Firm"), ("Aoede", "Breezy"),
	("Callirrhoe", "Easy-going"), ("Autonoe", "Bright"), ("Enceladus", "Breathy"), ("Iapetus", "Clear"),
	("Umbriel", "Easy-going"), ("Algieba", "Smooth"), ("Despina", "Smooth"), ("Erinome", "Clear"),
	("Algenib", "Gravelly"), ("Rasalgethi", "Informative"), ("Laomedeia", "Upbeat"), ("Achernar", "Soft"),
	("Alnilam", "Firm"), ("Schedar", "Even"), ("Gacrux", "Mature"), ("Pulcherrima", "Forward"),
	("Achird", "Friendly"), ("Zubenelgenubi", "Casual"), ("Vindemiatrix", "Gentle"), ("Sadachbia", "Lively"),
	("Sadaltager", "Knowledgeable"), ("Sulafat", "Warm"),
]
VOICE_LABELS = ["%s - %s" % v for v in VOICES]
VOICE_NAMES = [v[0] for v in VOICES]

# Newest first. If a model is not available for the key, the next one is tried automatically.
TTS_MODELS = ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview",
	"gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]
_state = {"model": None}
CHUNK = 2500


class _ModelUnavailable(Exception):
	pass


def gemini_key():
	try:
		return (providers.load().get("keys", {}).get("gemini") or "").strip()
	except Exception:
		return ""


NO_KEY = _("No Gemini API key is set. Open NVDA settings, choose the My assistant category, select "
	"Google Gemini as the AI provider and enter your API key. Then run this tool again.")


# ------------------------------------------------------------------ audio helpers (pure Python)
def make_wav(pcm, rate=24000, channels=1, bits=16):
	byte_rate = rate * channels * bits // 8
	align = channels * bits // 8
	head = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
	head += b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate, byte_rate, align, bits)
	head += b"data" + struct.pack("<I", len(pcm))
	return head + pcm


def parse_audio(data, mime=""):
	"""Return (pcm bytes, rate, channels, bits) from a WAV file or from raw 16-bit PCM."""
	if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
		rate, channels, bits = 24000, 1, 16
		pos = 12
		while pos + 8 <= len(data):
			cid = data[pos:pos + 4]
			size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
			body = pos + 8
			if cid == b"fmt " and body + 16 <= len(data):
				_f, channels, rate, _br, _al, bits = struct.unpack("<HHIIHH", data[body:body + 16])
			elif cid == b"data":
				end = body + size
				if size == 0 or size == 0xFFFFFFFF or end > len(data):
					end = len(data)
				return data[body:end], rate, channels, bits
			pos = body + size + (size & 1)
		return data[44:], rate, channels, bits
	m = re.search(r"rate=(\d+)", mime or "")
	return data, int(m.group(1)) if m else 24000, 1, 16


def join_audio(parts):
	"""Join several (pcm, rate, channels, bits) pieces into one WAV file."""
	pcm = b"".join(p[0] for p in parts)
	_p, rate, ch, bits = parts[0]
	return make_wav(pcm, rate, ch, bits), len(pcm) / float(rate * ch * bits // 8)


def split_text(text, limit=CHUNK):
	"""Cut long text at sentence ends so each request stays small."""
	text = text.strip()
	if len(text) <= limit:
		return [text]
	pieces = re.split(r"(?<=[.!?\u3002\u0964])\s+|\n+", text)
	out, cur = [], ""
	for p in pieces:
		p = p.strip()
		if not p:
			continue
		while len(p) > limit:
			cut = p.rfind(" ", 0, limit)
			cut = cut if cut > 0 else limit
			if cur:
				out.append(cur)
				cur = ""
			out.append(p[:cut])
			p = p[cut:].strip()
		if cur and len(cur) + len(p) + 1 > limit:
			out.append(cur)
			cur = ""
		cur = (cur + " " + p).strip()
	if cur:
		out.append(cur)
	return out


# ------------------------------------------------------------------ the Gemini request
def _error_message(e):
	try:
		body = e.read().decode("utf-8", "replace")
		return json.loads(body).get("error", {}).get("message") or body[:300]
	except Exception:
		return ""


def _request(key, model, text, voice):
	url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
	payload = {
		"contents": [{"parts": [{"text": text}]}],
		"generationConfig": {
			"responseModalities": ["AUDIO"],
			"speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
		},
	}
	req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST", headers={
		"Content-Type": "application/json", "x-goog-api-key": key, "User-Agent": "NVDA-MyAssistant/1.0"})
	try:
		with urllib.request.urlopen(req, timeout=180) as r:
			data = json.loads(r.read().decode("utf-8"))
	except urllib.error.HTTPError as e:
		msg = _error_message(e)
		low = msg.lower()
		if e.code == 404 or "not found" in low or "not supported" in low:
			raise _ModelUnavailable(msg)
		if e.code in (401, 403) or "api key" in low:
			raise RuntimeError(_("Gemini did not accept the API key. Check the key in NVDA settings, My assistant. %s") % msg)
		if e.code == 429:
			raise RuntimeError(_("The Gemini usage limit was reached. Wait a little and try again. %s") % msg)
		raise RuntimeError(_("Gemini error (HTTP %d). %s") % (e.code, msg))
	except urllib.error.URLError as e:
		raise RuntimeError(_("Connection failed: %s") % e.reason)
	for cand in data.get("candidates", []):
		for part in (cand.get("content") or {}).get("parts", []):
			inl = part.get("inlineData") or part.get("inline_data")
			if inl and inl.get("data"):
				return parse_audio(base64.b64decode(inl["data"]), inl.get("mimeType") or inl.get("mime_type") or "")
	block = (data.get("promptFeedback") or {}).get("blockReason")
	raise RuntimeError(_("Gemini returned no audio.") + (" (%s)" % block if block else ""))


def _one(key, text, voice):
	models = list(TTS_MODELS)
	if _state["model"] in models:
		models.remove(_state["model"])
		models.insert(0, _state["model"])
	last = ""
	for model in models:
		try:
			audio = _request(key, model, text, voice)
			_state["model"] = model
			return audio
		except _ModelUnavailable as e:
			last = str(e)
	raise RuntimeError(_("No Gemini speech model could be used with this API key. %s") % last)


def generate(key, text, voice):
	"""Returns (WAV bytes, seconds). Raises RuntimeError with a readable message."""
	parts = [_one(key, piece, voice) for piece in split_text(text)]
	return join_audio(parts)


# ------------------------------------------------------------------ dialogs
def _temp_wav(wav):
	fd, path = tempfile.mkstemp(prefix="myAssistant_", suffix=".wav")
	with os.fdopen(fd, "wb") as f:
		f.write(wav)
	return path


def _play(path):
	try:
		import nvwave
		nvwave.playWaveFile(path, asynchronous=True)
	except Exception:
		pass


class _TextDialog(wx.Dialog):
	def __init__(self):
		super().__init__(gui.mainFrame, title=_("AI: Gemini voices text to speech"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		s = wx.BoxSizer(wx.VERTICAL)
		h = guiHelper.BoxSizerHelper(self, sizer=s)
		self.text = h.addLabeledControl(_("&Enter your text:"), wx.TextCtrl, style=wx.TE_MULTILINE, size=(560, 180))
		self.voice = h.addLabeledControl(_("Choose your &voice:"), wx.ComboBox, choices=VOICE_LABELS, style=wx.CB_READONLY)
		self.voice.SetSelection(0)
		bh = guiHelper.ButtonHelper(wx.HORIZONTAL)
		gen = bh.addButton(self, id=wx.ID_OK, label=_("&Generate Audio"))
		cl = bh.addButton(self, id=wx.ID_CANCEL, label=_("&Cancel"))
		gen.Bind(wx.EVT_BUTTON, self.onGenerate)
		cl.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
		self.SetEscapeId(wx.ID_CANCEL)
		h.addItem(bh)
		_finish(self, s)
		self.text.SetFocus()

	def onGenerate(self, evt):
		if not self.text.GetValue().strip():
			speak(_("Please enter some text first"))
			sounds.play("error")
			self.text.SetFocus()
			return
		self.EndModal(wx.ID_OK)


class _ResultDialog(wx.Dialog):
	def __init__(self, wav, path, voice, seconds):
		super().__init__(gui.mainFrame, title=_("AI: Gemini voices text to speech"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.wav, self.path = wav, path
		s = wx.BoxSizer(wx.VERTICAL)
		h = guiHelper.BoxSizerHelper(self, sizer=s)
		summary = _("Audio file is playing. Voice: %s. Length: %.1f seconds. "
			"Press Save Audio to save it as a WAV file.") % (voice.split(" - ")[0], seconds)
		self.result = h.addLabeledControl(_("Result:"), wx.TextCtrl, value=summary,
			style=wx.TE_MULTILINE | wx.TE_READONLY, size=(520, 100))
		bh = guiHelper.ButtonHelper(wx.HORIZONTAL)
		save = bh.addButton(self, label=_("&Save Audio"))
		again = bh.addButton(self, label=_("&Play again"))
		cl = bh.addButton(self, id=wx.ID_CLOSE, label=_("C&lose"))
		save.Bind(wx.EVT_BUTTON, self.onSave)
		again.Bind(wx.EVT_BUTTON, lambda e: _play(self.path))
		cl.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
		self.SetEscapeId(wx.ID_CLOSE)
		h.addItem(bh)
		_finish(self, s)
		self.result.SetFocus()

	def onSave(self, evt):
		dlg = wx.FileDialog(self, _("Choose where to save the WAV file"), defaultFile="gemini_speech.wav",
			wildcard=_("WAV audio (*.wav)|*.wav"), style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
		try:
			if dlg.ShowModal() != wx.ID_OK:
				return
			target = dlg.GetPath()
		finally:
			dlg.Destroy()
		if not target.lower().endswith(".wav"):
			target += ".wav"
		try:
			with open(target, "wb") as f:
				f.write(self.wav)
		except OSError as e:
			sounds.play("error")
			wx.MessageBox(_("The file could not be saved: %s") % e, _("Save Audio"), wx.OK | wx.ICON_ERROR, self)
			return
		sounds.play("success")
		speak(_("Audio saved"))
		self.result.SetValue(_("Audio saved to %s") % target)
		self.result.SetFocus()


def tool_gemini_tts():
	title = _("AI: Gemini voices text to speech")
	key = gemini_key()
	if not key:
		show_text(title, NO_KEY)
		return
	sounds.play("open")
	got = _modal(_TextDialog(), lambda d, code: (d.text.GetValue().strip(), VOICE_LABELS[max(d.voice.GetSelection(), 0)])
		if code == wx.ID_OK else None)
	if not got:
		sounds.play("close")
		return
	text, voice = got
	speak(_("Please wait"))
	sounds.play("working")

	def work():
		return generate(key, text, voice.split(" - ")[0])

	def done(res):
		if not isinstance(res, tuple):
			sounds.play("error")
			show_text(title, res)
			return
		wav, seconds = res
		path = _temp_wav(wav)
		_play(path)
		try:
			_modal(_ResultDialog(wav, path, voice, seconds))
		finally:
			sounds.play("close")
			try:
				os.remove(path)
			except OSError:
				pass
	bg(work, done)

# -*- coding: UTF-8 -*-
"""AI: Gemini Live Assistant.

Press Start Conversation and talk to Gemini out loud; Gemini answers with its voice. Press Share Screen
and Gemini can also see your screen, so you can ask it what is on the screen or to read something.

How it works: a WebSocket connection to the Gemini Live API. The microphone (16 kHz) is streamed to
Gemini, Gemini's voice (24 kHz) is played through NVDA's audio output, and screenshots are sent as
JPEG pictures about every two seconds while sharing is on.
"""
import base64
import hashlib
import json
import os
import queue
import tempfile
import threading
import wx
import gui
import addonHandler
from gui import guiHelper
from logHandler import log
from . import sounds
from .common import speak, show_text, _finish, _modal
from .gemini_tts import gemini_key, NO_KEY
from .wsclient import WebSocket, WebSocketError, HandshakeError

addonHandler.initTranslation()

# Newest first. If a model is not available for the key, the next one is tried.
LIVE_MODELS = ["gemini-3.8-live", "gemini-3.1-flash-live-preview", "gemini-2.5-flash-native-audio-preview-12-2025"]
WS_URL = ("wss://generativelanguage.googleapis.com/ws/"
	"google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=%s")
SYSTEM = ("You are a friendly voice assistant inside a screen reader add-on. The user is blind and uses the NVDA "
	"screen reader. Speak clearly and keep answers short, because they are heard, not read. "
	"When the user shares their screen you receive pictures of it: describe what is on the screen, read text aloud "
	"when asked, and say which buttons, links and fields are available and how to reach them with the keyboard. "
	"If you cannot see the screen, say that the user should press Share Screen.")
MAX_WIDTH = 1600
SHARE_SECONDS = 2.0


# ------------------------------------------------------------------ screen capture
def _grab(holder, done):
	"""Runs on NVDA's main thread (wx is not thread safe)."""
	try:
		w, h = wx.GetDisplaySize()
		screen = wx.ScreenDC()
		bmp = wx.Bitmap(w, h)
		mem = wx.MemoryDC()
		mem.SelectObject(bmp)
		mem.Blit(0, 0, w, h, screen, 0, 0)
		mem.SelectObject(wx.NullBitmap)
		img = bmp.ConvertToImage()
		if w > MAX_WIDTH:
			img = img.Scale(MAX_WIDTH, max(1, int(h * MAX_WIDTH / w)), wx.IMAGE_QUALITY_HIGH)
		img.SetOption(wx.IMAGE_OPTION_QUALITY, 70)
		fd, path = tempfile.mkstemp(suffix=".jpg")
		os.close(fd)
		try:
			img.SaveFile(path, wx.BITMAP_TYPE_JPEG)
			with open(path, "rb") as f:
				holder["data"] = f.read()
		finally:
			try:
				os.remove(path)
			except OSError:
				pass
	except Exception as e:
		holder["error"] = str(e)
	finally:
		done.set()


def capture_screen_jpeg(timeout=10):
	holder, done = {}, threading.Event()
	wx.CallAfter(_grab, holder, done)
	if not done.wait(timeout):
		raise RuntimeError("The screen could not be captured in time.")
	if "error" in holder:
		raise RuntimeError(holder["error"])
	return holder["data"]


# ------------------------------------------------------------------ the live session
def _setup(model, layout):
	"""The first message. Layouts differ only in where the settings go, so a server that wants them
	somewhere else is still understood (layout 0 follows Google's WebSocket guide)."""
	cfg = {"model": "models/" + model, "systemInstruction": {"parts": [{"text": SYSTEM}]}}
	if layout == 0:
		cfg["responseModalities"] = ["AUDIO"]
		cfg["inputAudioTranscription"] = {}
		cfg["outputAudioTranscription"] = {}
	elif layout == 1:
		cfg["generationConfig"] = {"responseModalities": ["AUDIO"]}
		cfg["inputAudioTranscription"] = {}
		cfg["outputAudioTranscription"] = {}
	else:
		cfg["generationConfig"] = {"responseModalities": ["AUDIO"]}
	return {"setup": cfg}


class LiveSession(object):
	"""One conversation. All events reach the dialog on the main thread through on_event(session, kind, text)."""

	def __init__(self, key, on_event):
		self.key = key
		self.on_event = on_event
		self.ws = None
		self.mic = None
		self.live = False
		self.sharing = False
		self._stop = threading.Event()
		self._stopped = False
		self._ended = False
		self._lock = threading.Lock()
		self._wake = threading.Event()
		self._audio = queue.Queue()
		self._user = ""
		self._model = ""
		self._last = None

	def emit(self, kind, text=""):
		try:
			wx.CallAfter(self.on_event, self, kind, text)
		except Exception:
			pass

	def start(self):
		threading.Thread(target=self._run, daemon=True).start()

	# -- control (main thread)
	def set_sharing(self, on):
		self.sharing = bool(on)
		self._last = None
		self._wake.set()

	def stop(self):
		with self._lock:
			if self._stopped:
				return
			self._stopped = True
		self._stop.set()
		self._wake.set()
		self._audio.put(None)
		try:
			if self.ws:
				self.ws.close()
		except Exception:
			pass
		mic, self.mic = self.mic, None
		if mic:
			threading.Thread(target=mic.stop, daemon=True).start()

	def _fail(self, text):
		if self._stop.is_set():
			return
		self.emit("error", text)
		self.stop()

	# -- connecting
	def _connect(self):
		last = ""
		for model in LIVE_MODELS:
			for layout in (0, 1, 2):
				if self._stop.is_set():
					raise RuntimeError(_("Cancelled."))
				try:
					ws = WebSocket(WS_URL % self.key)
				except HandshakeError as e:
					text = str(e)
					if " 400" in text or " 401" in text or " 403" in text:
						raise RuntimeError(_("Gemini did not accept the API key. Check the key in NVDA settings, "
							"My assistant. (%s)") % text[:200])
					raise RuntimeError(_("Gemini refused the connection: %s") % text[:300])
				except (OSError, WebSocketError) as e:
					raise RuntimeError(_("Connection failed: %s") % e)
				try:
					ws.send_text(json.dumps(_setup(model, layout)))
					self._wait_setup(ws)
				except (OSError, WebSocketError) as e:
					last = str(e)
					ws.close()
					low = last.lower()
					if "model" in low and ("not found" in low or "not supported" in low):
						break
					continue
				self.ws = ws
				return
		raise RuntimeError(_("Gemini Live could not start. %s") % last[:400])

	def _wait_setup(self, ws):
		import time
		deadline = time.time() + 20
		while time.time() < deadline:
			if self._stop.is_set():
				raise WebSocketError("Cancelled.")
			msg = ws.recv(1.0)
			if msg is None:
				continue
			try:
				data = json.loads(msg)
			except ValueError:
				continue
			if "setupComplete" in data:
				return
			if "error" in data:
				raise WebSocketError(str(data["error"]))
		raise WebSocketError("Gemini did not answer in time.")

	# -- the worker
	def _run(self):
		try:
			self._connect()
		except Exception as e:
			self._fail(str(e))
			self._finish()
			return
		if self._stop.is_set():
			self.stop()
			self._finish()
			return
		threading.Thread(target=self._playback, daemon=True).start()
		try:
			from .winaudio import Microphone
			self.mic = Microphone(self._on_mic)
			self.mic.start()
		except Exception as e:
			self._fail(str(e))
			self._finish()
			return
		threading.Thread(target=self._screen_loop, daemon=True).start()
		self.live = True
		self.emit("live")
		try:
			while not self._stop.is_set():
				msg = self.ws.recv(1.0)
				if msg is not None:
					self._handle(msg)
		except Exception as e:
			if not self._stop.is_set():
				log.debugWarning("My assistant: live session ended", exc_info=True)
				self._fail(_("The conversation ended. %s") % e)
		self.stop()
		self._finish()

	def _finish(self):
		if not self._ended:
			self._ended = True
			self.emit("ended")

	def _handle(self, msg):
		try:
			data = json.loads(msg)
		except ValueError:
			return
		sc = data.get("serverContent")
		if sc:
			for part in (sc.get("modelTurn") or {}).get("parts", []):
				inl = part.get("inlineData")
				if inl and inl.get("data"):
					try:
						self._audio.put(base64.b64decode(inl["data"]))
					except Exception:
						pass
			t = (sc.get("inputTranscription") or {}).get("text")
			if t:
				self._user += t
			t = (sc.get("outputTranscription") or {}).get("text")
			if t:
				if self._user.strip():
					self._flush()
				self._model += t
			if sc.get("interrupted"):
				self._clear_audio()
			if sc.get("turnComplete") or sc.get("interrupted"):
				self._flush()
		if data.get("goAway"):
			self.emit("status", _("Gemini will end this conversation soon. Start a new one to continue."))

	def _flush(self):
		user, model = self._user.strip(), self._model.strip()
		self._user = self._model = ""
		if user:
			self.emit("user", user)
		if model:
			self.emit("model", model)

	# -- microphone, playback, screen
	def _on_mic(self, data):
		ws = self.ws
		if self._stop.is_set() or ws is None:
			return
		try:
			ws.send_text(json.dumps({"realtimeInput": {"audio": {
				"data": base64.b64encode(data).decode("ascii"), "mimeType": "audio/pcm;rate=16000"}}}))
		except Exception as e:
			self._fail(_("The connection to Gemini was lost. %s") % e)

	def _clear_audio(self):
		if self._stop.is_set():
			return
		try:
			while True:
				self._audio.get_nowait()
		except queue.Empty:
			pass
		self._audio.put("clear")

	def _playback(self):
		player = None
		try:
			import nvwave
			while True:
				item = self._audio.get()
				if item is None:
					break
				if item == "clear":
					if player:
						player.stop()
					continue
				if player is None:
					try:
						player = nvwave.WavePlayer(channels=1, samplesPerSec=24000, bitsPerSample=16, wantDucking=False)
					except TypeError:
						player = nvwave.WavePlayer(channels=1, samplesPerSec=24000, bitsPerSample=16)
				player.feed(item)
		except Exception:
			log.error("My assistant: live audio playback failed", exc_info=True)
		finally:
			if player:
				try:
					player.stop()
					player.close()
				except Exception:
					pass

	def _screen_loop(self):
		while not self._stop.is_set():
			self._wake.wait(SHARE_SECONDS)
			self._wake.clear()
			if self._stop.is_set():
				break
			if not self.sharing or self.ws is None:
				continue
			try:
				jpg = capture_screen_jpeg()
				digest = hashlib.md5(jpg).digest()
				if digest == self._last:
					continue
				self._last = digest
				self.ws.send_text(json.dumps({"realtimeInput": {"video": {
					"data": base64.b64encode(jpg).decode("ascii"), "mimeType": "image/jpeg"}}}))
			except Exception as e:
				if not self._stop.is_set():
					log.debugWarning("My assistant: sharing the screen failed", exc_info=True)
					self.sharing = False
					self.emit("sharing_failed", str(e))


# ------------------------------------------------------------------ the dialog
class LiveDialog(wx.Dialog):
	def __init__(self, key):
		super().__init__(gui.mainFrame, title=_("AI: Gemini Live Assistant"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.key = key
		self.session = None
		self.sharing = False
		s = wx.BoxSizer(wx.VERTICAL)
		h = guiHelper.BoxSizerHelper(self, sizer=s)
		h.addItem(wx.StaticText(self, label=_("Press Start Conversation, then talk to Gemini. "
			"Use headphones so that Gemini does not hear its own voice. "
			"Share Screen sends pictures of your screen to Google Gemini.")))
		self.log = h.addLabeledControl(_("Conversation:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY, size=(560, 220))
		bh = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.startBtn = bh.addButton(self, label=_("Start &Conversation"))
		self.shareBtn = bh.addButton(self, label=_("Share &Screen"))
		self.closeBtn = bh.addButton(self, id=wx.ID_CLOSE, label=_("C&lose"))
		self.startBtn.Bind(wx.EVT_BUTTON, self.onStart)
		self.shareBtn.Bind(wx.EVT_BUTTON, self.onShare)
		self.closeBtn.Bind(wx.EVT_BUTTON, self.onCloseButton)
		self.Bind(wx.EVT_CLOSE, self.onWindowClose)
		self.SetEscapeId(wx.ID_CLOSE)
		h.addItem(bh)
		_finish(self, s)
		self.startBtn.SetFocus()

	def shutdown(self):
		"""Safe to call at any time, even after the window is gone."""
		session, self.session = self.session, None
		if session:
			session.stop()

	def add(self, text):
		self.log.AppendText(text + "\n")

	def _reset(self):
		self.session = None
		self.sharing = False
		self.startBtn.SetLabel(_("Start &Conversation"))
		self.shareBtn.SetLabel(_("Share &Screen"))

	# -- buttons
	def onStart(self, evt):
		if self.session:
			self.session.stop()
			self._reset()
			sounds.play("close")
			speak(_("Conversation stopped"))
			self.add(_("Conversation stopped."))
			return
		self.session = LiveSession(self.key, self.onEvent)
		self.startBtn.SetLabel(_("Stop &Conversation"))
		sounds.play("working")
		speak(_("Connecting to Gemini. Please wait."))
		self.add(_("Connecting to Gemini..."))
		self.session.start()

	def onShare(self, evt):
		if not self.session or not self.session.live:
			sounds.play("error")
			speak(_("Start the conversation first"))
			return
		self.sharing = not self.sharing
		self.session.set_sharing(self.sharing)
		if self.sharing:
			self.shareBtn.SetLabel(_("Stop sharing &screen"))
			sounds.play("sweep")
			msg = _("Screen sharing started. Gemini can see your screen now.")
		else:
			self.shareBtn.SetLabel(_("Share &Screen"))
			sounds.play("close")
			msg = _("Screen sharing stopped.")
		speak(msg)
		self.add(msg)

	def onCloseButton(self, evt):
		self.shutdown()
		self.EndModal(wx.ID_CLOSE)

	def onWindowClose(self, evt):
		self.shutdown()
		evt.Skip()

	# -- events from the session
	def onEvent(self, session, kind, text):
		if session is not self.session:
			return
		try:
			if kind == "live":
				sounds.play("notify")
				msg = _("Gemini is live. You can speak now.")
				speak(msg)
				self.add(msg)
			elif kind == "status":
				speak(text)
				self.add(text)
			elif kind == "user":
				self.add(_("You: %s") % text)
			elif kind == "model":
				self.add(_("Gemini: %s") % text)
			elif kind == "sharing_failed":
				self.sharing = False
				self.shareBtn.SetLabel(_("Share &Screen"))
				sounds.play("error")
				msg = _("Screen sharing stopped because the screen could not be sent. %s") % text
				speak(msg)
				self.add(msg)
			elif kind == "error":
				self._reset()
				sounds.play("error")
				speak(text)
				self.add(text)
			elif kind == "ended":
				self._reset()
				speak(_("Conversation ended"))
				self.add(_("Conversation ended."))
		except RuntimeError:
			pass


def tool_gemini_live():
	title = _("AI: Gemini Live Assistant")
	key = gemini_key()
	if not key:
		show_text(title, NO_KEY)
		return
	dlg = LiveDialog(key)
	sounds.play("open")
	try:
		_modal(dlg)
	finally:
		dlg.shutdown()
		sounds.play("close")

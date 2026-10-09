# -*- coding: UTF-8 -*-
"""Microphone capture using the Windows waveIn API through ctypes (no extra libraries needed).

Audio is delivered as raw 16-bit mono PCM in small chunks to the on_data callback, which is
called from a background thread.
"""
import ctypes
import threading
import time
from ctypes import wintypes

WAVE_FORMAT_PCM = 1
WAVE_MAPPER = 0xFFFFFFFF
WHDR_DONE = 0x00000001
MMSYSERR_NOERROR = 0


class WAVEFORMATEX(ctypes.Structure):
	_pack_ = 1
	_fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD),
		("nSamplesPerSec", wintypes.DWORD), ("nAvgBytesPerSec", wintypes.DWORD),
		("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD), ("cbSize", wintypes.WORD)]


class WAVEHDR(ctypes.Structure):
	_fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD),
		("dwBytesRecorded", wintypes.DWORD), ("dwUser", ctypes.c_size_t), ("dwFlags", wintypes.DWORD),
		("dwLoops", wintypes.DWORD), ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]


_dll = {}


def _winmm():
	if "dll" not in _dll:
		w = ctypes.WinDLL("winmm")
		hw = ctypes.c_void_p
		w.waveInOpen.argtypes = [ctypes.POINTER(hw), wintypes.UINT, ctypes.POINTER(WAVEFORMATEX),
			ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
		w.waveInOpen.restype = wintypes.UINT
		for name in ("waveInPrepareHeader", "waveInUnprepareHeader", "waveInAddBuffer"):
			f = getattr(w, name)
			f.argtypes = [hw, ctypes.POINTER(WAVEHDR), wintypes.UINT]
			f.restype = wintypes.UINT
		for name in ("waveInStart", "waveInStop", "waveInReset", "waveInClose"):
			f = getattr(w, name)
			f.argtypes = [hw]
			f.restype = wintypes.UINT
		_dll["dll"] = w
	return _dll["dll"]


class Microphone(object):
	"""Records from the default microphone until stop() is called."""

	def __init__(self, on_data, rate=16000, chunk_ms=100, buffers=6):
		self.on_data = on_data
		self.rate = rate
		self.size = int(rate * 2 * chunk_ms / 1000)
		self.count = buffers
		self._stop = threading.Event()
		self._thread = None
		self._handle = None
		self._bufs = []
		self._hdrs = []

	def start(self):
		w = _winmm()
		fmt = WAVEFORMATEX(WAVE_FORMAT_PCM, 1, self.rate, self.rate * 2, 2, 16, 0)
		handle = ctypes.c_void_p()
		res = w.waveInOpen(ctypes.byref(handle), WAVE_MAPPER, ctypes.byref(fmt), 0, 0, 0)
		if res != MMSYSERR_NOERROR:
			raise RuntimeError("The microphone could not be opened (Windows error %d). "
				"Check that a microphone is connected and that Windows allows apps to use it." % res)
		self._handle = handle
		hdr_size = ctypes.sizeof(WAVEHDR)
		for _i in range(self.count):
			buf = ctypes.create_string_buffer(self.size)
			hdr = WAVEHDR()
			hdr.lpData = ctypes.addressof(buf)
			hdr.dwBufferLength = self.size
			self._bufs.append(buf)
			self._hdrs.append(hdr)
			w.waveInPrepareHeader(handle, ctypes.byref(hdr), hdr_size)
			w.waveInAddBuffer(handle, ctypes.byref(hdr), hdr_size)
		res = w.waveInStart(handle)
		if res != MMSYSERR_NOERROR:
			self._release()
			raise RuntimeError("The microphone could not be started (Windows error %d)." % res)
		self._thread = threading.Thread(target=self._loop, daemon=True)
		self._thread.start()

	def _loop(self):
		w = _winmm()
		hdr_size = ctypes.sizeof(WAVEHDR)
		while not self._stop.is_set():
			busy = False
			for hdr in self._hdrs:
				if hdr.dwFlags & WHDR_DONE:
					n = hdr.dwBytesRecorded
					data = ctypes.string_at(hdr.lpData, n) if n else b""
					hdr.dwBytesRecorded = 0
					w.waveInAddBuffer(self._handle, ctypes.byref(hdr), hdr_size)
					busy = True
					if data:
						try:
							self.on_data(data)
						except Exception:
							pass
			if not busy:
				time.sleep(0.01)

	def _release(self):
		w = _winmm()
		handle, self._handle = self._handle, None
		if not handle:
			return
		hdr_size = ctypes.sizeof(WAVEHDR)
		try:
			w.waveInStop(handle)
			w.waveInReset(handle)
			for hdr in self._hdrs:
				w.waveInUnprepareHeader(handle, ctypes.byref(hdr), hdr_size)
			w.waveInClose(handle)
		except Exception:
			pass
		self._hdrs = []
		self._bufs = []

	def stop(self):
		self._stop.set()
		if self._thread and self._thread is not threading.current_thread():
			self._thread.join(timeout=2)
		self._release()

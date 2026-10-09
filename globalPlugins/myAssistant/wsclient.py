# -*- coding: UTF-8 -*-
"""A small WebSocket client (RFC 6455) that uses only the Python standard library.

NVDA does not ship a WebSocket library, so the Live Assistant uses this one. It supports text and
binary messages, fragmented messages, ping and pong, and a clean close.
"""
import base64
import os
import select
import socket
import ssl
import struct
import threading
from urllib.parse import urlparse


class WebSocketError(Exception):
	"""The connection failed or was closed by the other side."""


class HandshakeError(WebSocketError):
	"""The server refused to upgrade the connection (for example a wrong API key)."""


def _mask(data, mask):
	if not data:
		return b""
	n = len(data)
	key = (mask * (n // 4 + 1))[:n]
	return (int.from_bytes(data, "big") ^ int.from_bytes(key, "big")).to_bytes(n, "big")


class WebSocket(object):
	def __init__(self, url, timeout=20):
		u = urlparse(url)
		secure = u.scheme == "wss"
		host = u.hostname
		port = u.port or (443 if secure else 80)
		path = (u.path or "/") + ("?" + u.query if u.query else "")
		raw = socket.create_connection((host, port), timeout)
		if secure:
			raw = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
		self.sock = raw
		self.sock.settimeout(timeout)
		self._buf = bytearray()
		self._lock = threading.Lock()
		self.closed = False
		key = base64.b64encode(os.urandom(16)).decode("ascii")
		head = ("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
			"Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n") % (path, host, key)
		self.sock.sendall(head.encode("ascii"))
		data = b""
		while b"\r\n\r\n" not in data:
			chunk = self.sock.recv(4096)
			if not chunk:
				self._drop()
				raise HandshakeError("The server closed the connection before the handshake finished.")
			data += chunk
			if len(data) > 65536:
				self._drop()
				raise HandshakeError("The server sent an unexpected reply.")
		head_bytes, rest = data.split(b"\r\n\r\n", 1)
		status = head_bytes.split(b"\r\n", 1)[0].decode("latin-1")
		if " 101" not in status:
			body = rest
			try:
				self.sock.settimeout(2)
				while len(body) < 1500:
					chunk = self.sock.recv(1500)
					if not chunk:
						break
					body += chunk
			except Exception:
				pass
			self._drop()
			raise HandshakeError("%s %s" % (status, body.decode("utf-8", "replace").strip()[:400]))
		self._buf.extend(rest)

	def _drop(self):
		self.closed = True
		try:
			self.sock.close()
		except Exception:
			pass

	# -- receiving
	def _fill(self, n, wait, idle_ok):
		"""Buffer at least n bytes. Returns False only when idle_ok is set and nothing arrived in time."""
		while len(self._buf) < n:
			if self.closed:
				raise WebSocketError("The connection is closed.")
			pending = getattr(self.sock, "pending", None)
			if not (pending and pending()):
				ready = select.select([self.sock], [], [], wait)[0]
				if not ready:
					if idle_ok and not self._buf:
						return False
					continue
			chunk = self.sock.recv(65536)
			if not chunk:
				self._drop()
				raise WebSocketError("The connection was closed.")
			self._buf.extend(chunk)
		return True

	def recv(self, wait=1.0):
		"""Return the next message as text, or None if nothing arrived within wait seconds."""
		message = None
		while True:
			if not self._fill(2, wait, message is None):
				return None
			b1, b2 = self._buf[0], self._buf[1]
			fin, op = b1 & 0x80, b1 & 0x0F
			ln = b2 & 0x7F
			idx = 2
			if ln == 126:
				self._fill(4, wait, False)
				ln = struct.unpack(">H", bytes(self._buf[2:4]))[0]
				idx = 4
			elif ln == 127:
				self._fill(10, wait, False)
				ln = struct.unpack(">Q", bytes(self._buf[2:10]))[0]
				idx = 10
			mask = None
			if b2 & 0x80:
				self._fill(idx + 4, wait, False)
				mask = bytes(self._buf[idx:idx + 4])
				idx += 4
			self._fill(idx + ln, wait, False)
			payload = bytes(self._buf[idx:idx + ln])
			del self._buf[:idx + ln]
			if mask:
				payload = _mask(payload, mask)
			if op == 0x8:
				code, reason = None, ""
				if len(payload) >= 2:
					code = struct.unpack(">H", payload[:2])[0]
					reason = payload[2:].decode("utf-8", "replace")
				try:
					self._send(0x8, payload[:2])
				except Exception:
					pass
				self._drop()
				raise WebSocketError("The server closed the connection (code %s). %s" % (code, reason))
			if op == 0x9:
				self._send(0xA, payload)
				continue
			if op == 0xA:
				continue
			if op in (0x1, 0x2):
				message = bytearray(payload)
			elif op == 0x0 and message is not None:
				message.extend(payload)
			if fin and message is not None:
				return bytes(message).decode("utf-8", "replace")

	# -- sending
	def _send(self, op, payload):
		n = len(payload)
		header = bytearray([0x80 | op])
		if n < 126:
			header.append(0x80 | n)
		elif n < 65536:
			header.append(0x80 | 126)
			header += struct.pack(">H", n)
		else:
			header.append(0x80 | 127)
			header += struct.pack(">Q", n)
		mask = os.urandom(4)
		header += mask
		frame = bytes(header) + _mask(payload, mask)
		with self._lock:
			self.sock.sendall(frame)

	def send_text(self, text):
		if self.closed:
			raise WebSocketError("The connection is closed.")
		self._send(0x1, text.encode("utf-8"))

	def close(self):
		if self.closed:
			return
		try:
			self._send(0x8, struct.pack(">H", 1000))
		except Exception:
			pass
		self._drop()

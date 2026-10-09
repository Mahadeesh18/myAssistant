# -*- coding: UTF-8 -*-
"""Website inspector: a very advanced internet tool that needs no account or API key.

It checks one website or domain like a security and performance auditor and explains every
finding in plain language for a screen reader user:
  * redirect trace (every hop, loops, HTTP to HTTPS upgrade)
  * TLS connection: protocol version, cipher, HTTP/2, certificate owner, issuer, expiry, names
  * security headers (HSTS, CSP, frame, MIME sniffing, referrer, permissions) and cookie flags
  * speed: DNS, connection, TLS, server wait and download times, page size, compression, caching
  * technology and hosting clues (CDN, server, generator, IP owner and country)
  * DNS records with DNSSEC and CAA
  * email domain security: SPF, DKIM, DMARC, MX, MTA-STS
  * security.txt and robots.txt
A score and a "fix first" list are placed at the top so the most important part is read first.
"""
import http.client
import os
import re
import socket
import ssl
import tempfile
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urljoin, quote
import addonHandler
from .common import run_async, ask_form, http_json, UA

addonHandler.initTranslation()

REDIRECTS = (301, 302, 303, 307, 308)
DKIM_SELECTORS = ["default", "google", "selector1", "selector2", "k1", "k2", "s1", "s2", "mail", "dkim",
	"smtp", "mandrill", "mxvault", "zoho", "protonmail"]
CDN_HEADERS = [
	("cf-ray", "Cloudflare"), ("x-amz-cf-id", "Amazon CloudFront"), ("x-served-by", "Fastly or Varnish cache"),
	("x-vercel-id", "Vercel"), ("x-nf-request-id", "Netlify"), ("x-github-request-id", "GitHub Pages"),
	("x-azure-ref", "Microsoft Azure Front Door"), ("x-goog-generation", "Google Cloud Storage"),
	("x-akamai-transformed", "Akamai"), ("x-sucuri-id", "Sucuri"), ("x-wix-request-id", "Wix"),
	("x-shopify-stage", "Shopify"), ("x-drupal-cache", "Drupal"), ("x-pingback", "WordPress"),
]


# ------------------------------------------------------------------ report helper
class _Report:
	def __init__(self):
		self.lines = []
		self.issues = []
		self.lost = {}
		self.group = None

	def h(self, title, group=None):
		if self.lines:
			self.lines.append("")
		self.lines.append(title.upper())
		self.group = group
		if group:
			self.lost.setdefault(group, 0)

	def add(self, text):
		self.lines.append(text)

	def pen(self, n):
		if self.group and n:
			self.lost[self.group] += n

	def good(self, text):
		self.lines.append("Good: " + text)

	def warn(self, text, lost=0, fix=None):
		self.lines.append("Warning: " + text)
		self.pen(lost)
		self.issues.append(("Warning", fix or text))

	def bad(self, text, lost=0, fix=None):
		self.lines.append("Problem: " + text)
		self.pen(lost)
		self.issues.append(("Problem", fix or text))

	def score(self, group):
		return max(0, 100 - self.lost.get(group, 0))


def _grade(score):
	for limit, letter in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
		if score >= limit:
			return letter
	return "F"


def _ms(seconds):
	return "%d ms" % round(seconds * 1000)


def _size(n):
	if n >= 1048576:
		return "%.1f MB" % (n / 1048576.0)
	if n >= 1024:
		return "%.0f KB" % (n / 1024.0)
	return "%d bytes" % n


# ------------------------------------------------------------------ addresses
def _target(raw):
	raw = (raw or "").strip()
	if not raw or re.search(r"\s", raw):
		raise ValueError("Please type one website address or domain without spaces.")
	explicit = bool(re.match(r"^https?://", raw, re.I))
	if not explicit:
		raw = "https://" + raw
	p = urlparse(raw)
	if not p.hostname:
		raise ValueError("That does not look like a web address.")
	port = p.port or (443 if p.scheme.lower() == "https" else 80)
	return raw, p.hostname.lower(), port, explicit


def _split(url):
	p = urlparse(url)
	path = p.path or "/"
	if p.query:
		path += "?" + p.query
	return p.scheme.lower(), p.hostname, p.port or (443 if p.scheme.lower() == "https" else 80), path


# ------------------------------------------------------------------ one HTTP request
def _hop(url, verify=True, limit=1000000):
	"""One GET request without following redirects. Times the connection, server wait and download."""
	scheme, host, port, path = _split(url)
	if scheme == "https":
		ctx = ssl.create_default_context() if verify else ssl._create_unverified_context()
		conn = http.client.HTTPSConnection(host, port, timeout=20, context=ctx)
	else:
		conn = http.client.HTTPConnection(host, port, timeout=20)
	try:
		t0 = time.time()
		conn.connect()
		t_conn = time.time() - t0
		t1 = time.time()
		conn.request("GET", path, headers={"User-Agent": UA["User-Agent"], "Accept": "text/html,*/*;q=0.8",
			"Accept-Encoding": "gzip", "Connection": "close"})
		resp = conn.getresponse()
		t_wait = time.time() - t1
		t2 = time.time()
		body = resp.read(limit)
		t_dl = time.time() - t2
		raw_headers = resp.getheaders()
		status, reason, version = resp.status, resp.reason, resp.version
	finally:
		conn.close()
	headers, cookies = {}, []
	for k, v in raw_headers:
		k = k.lower()
		if k == "set-cookie":
			cookies.append(v)
		headers[k] = (headers[k] + ", " + v) if k in headers else v
	encoding = headers.get("content-encoding", "").lower()
	decoded = body
	if "gzip" in encoding:
		try:
			decoded = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(body)
		except Exception:
			decoded = body
	return {"url": url, "status": status, "reason": reason, "version": version, "headers": headers,
		"cookies": cookies, "connect": t_conn, "wait": t_wait, "download": t_dl, "wire": len(body),
		"size": len(decoded), "truncated": len(body) >= limit, "encoding": encoding,
		"text": decoded[:300000].decode("utf-8", "replace")}


def _trace(start, max_hops=10):
	hops, seen, url, cert_errors, problem = [], set(), start, {}, None
	while True:
		seen.add(url)
		host = urlparse(url).hostname
		try:
			h = _hop(url, verify=host not in cert_errors)
		except ssl.SSLCertVerificationError as e:
			cert_errors[host] = getattr(e, "verify_message", None) or str(e)
			h = _hop(url, verify=False)
		hops.append(h)
		loc = h["headers"].get("location")
		if h["status"] in REDIRECTS and loc:
			nxt = urljoin(url, loc)
			if nxt in seen:
				problem = "loop"
				break
			if len(hops) >= max_hops:
				problem = "toomany"
				break
			url = nxt
			continue
		break
	return {"hops": hops, "problem": problem, "cert_errors": cert_errors}


# ------------------------------------------------------------------ TLS probe
def _decode_der(der):
	try:
		fd, path = tempfile.mkstemp(suffix=".pem")
		try:
			os.write(fd, ssl.DER_cert_to_PEM_cert(der).encode())
		finally:
			os.close(fd)
		try:
			return ssl._ssl._test_decode_cert(path)
		finally:
			os.remove(path)
	except Exception:
		return {}


def _probe(host, port):
	out = {}
	t = time.time()
	infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
	out["dns"] = time.time() - t
	out["ips"] = sorted({i[4][0] for i in infos})
	fam, _t, _p, _c, addr = infos[0]

	def connect():
		s = socket.socket(fam, socket.SOCK_STREAM)
		s.settimeout(15)
		t0 = time.time()
		s.connect(addr)
		return s, time.time() - t0

	s, out["tcp"] = connect()
	ctx = ssl.create_default_context()
	ctx.set_alpn_protocols(["h2", "http/1.1"])
	t = time.time()
	try:
		ss = ctx.wrap_socket(s, server_hostname=host)
		out["verified"] = True
	except ssl.SSLCertVerificationError as e:
		out["verified"] = False
		out["verify_error"] = getattr(e, "verify_message", None) or str(e)
		s.close()
		s, _x = connect()
		ctx = ssl._create_unverified_context()
		ctx.set_alpn_protocols(["h2", "http/1.1"])
		t = time.time()
		ss = ctx.wrap_socket(s, server_hostname=host)
	out["tls"] = time.time() - t
	try:
		out["version"] = ss.version()
		out["cipher"] = ss.cipher()
		out["alpn"] = ss.selected_alpn_protocol()
		cert = ss.getpeercert() if out["verified"] else None
		if not cert:
			cert = _decode_der(ss.getpeercert(binary_form=True))
		out["cert"] = cert or {}
	finally:
		ss.close()
	return out


def _covers(host, sans):
	for s in sans:
		s = s.lower()
		if s == host or (s.startswith("*.") and host.split(".", 1)[1:] == [s[2:]]):
			return True
	return False


# ------------------------------------------------------------------ sections
def _sec_redirects(rep, tr, start, explicit):
	rep.h("Redirect trace")
	hops = tr["hops"]
	for i, h in enumerate(hops, 1):
		line = "%d. %s: %d %s (server answered in %s)" % (i, h["url"], h["status"], h["reason"], _ms(h["wait"]))
		loc = h["headers"].get("location")
		if h["status"] in REDIRECTS and loc:
			line += ", moves to %s" % urljoin(h["url"], loc)
		rep.add(line)
	if tr["problem"] == "loop":
		rep.bad("The redirects go round in a circle, so the page never loads.", fix="Fix the redirect loop.")
	elif tr["problem"] == "toomany":
		rep.bad("More than 10 redirects in a row. Browsers give up after about 20 and visitors are slowed down.",
			fix="Shorten the redirect chain.")
	elif len(hops) == 1:
		rep.good("No redirects: the address answers directly.")
	elif len(hops) > 3:
		rep.warn("%d redirects before the final page. Each one adds waiting time." % (len(hops) - 1),
			fix="Reduce the number of redirects.")
	else:
		rep.add("%d redirect(s) before the final page." % (len(hops) - 1))
	fin = hops[-1]
	if fin["status"] >= 400:
		rep.bad("The final page answers with error %d %s." % (fin["status"], fin["reason"]),
			fix="The final page returns error %d." % fin["status"])
	return fin


def _sec_http_upgrade(rep, host):
	try:
		h = _hop("http://%s/" % host, limit=2000)
	except Exception as e:
		rep.add("Plain HTTP (port 80) could not be reached (%s). That is fine for a site that is HTTPS only." % e)
		return
	loc = urljoin(h["url"], h["headers"].get("location", "")) if h["status"] in REDIRECTS else ""
	if loc.lower().startswith("https://"):
		if h["status"] in (301, 308):
			rep.good("Plain HTTP is permanently redirected to HTTPS.")
		else:
			rep.warn("Plain HTTP is redirected to HTTPS, but with a temporary redirect (%d). Use 301 or 308." % h["status"],
				fix="Make the HTTP to HTTPS redirect permanent (301 or 308).")
	else:
		rep.bad("Plain HTTP is not redirected to HTTPS, so visitors who type the address without https are not protected.",
			5, "Redirect http:// to https://.")


def _sec_tls(rep, pr, final_scheme, host):
	rep.h("Encrypted connection and certificate", "web")
	if "error" in pr:
		rep.bad("HTTPS could not be used: %s" % pr["error"], 20, "Enable HTTPS with a valid certificate.")
		return
	lost = 0
	if final_scheme != "https":
		rep.bad("The final page is served over plain HTTP. Everything sent can be read or changed on the way.",
			fix="Serve the site over HTTPS.")
		lost += 20
	ver = pr.get("version") or "unknown"
	if ver in ("TLSv1.3", "TLSv1.2"):
		rep.good("Protocol %s." % ver.replace("TLSv", "TLS "))
	else:
		rep.bad("Old protocol %s is in use. Use TLS 1.2 or 1.3." % ver, fix="Disable old TLS versions.")
		lost += 10
	c = pr.get("cipher")
	if c:
		rep.add("Cipher: %s, %d-bit." % (c[0], c[2]))
	rep.add("HTTP/2: %s." % ("supported (faster for many files)" if pr.get("alpn") == "h2" else "not offered, the server uses HTTP/1.1"))
	cert = pr.get("cert") or {}
	if not pr.get("verified"):
		rep.bad("Your computer does not trust this certificate: %s." % pr.get("verify_error"),
			fix="Install a certificate from a trusted authority.")
		lost += 20
	subj = dict(x[0] for x in cert.get("subject", ()) if x)
	iss = dict(x[0] for x in cert.get("issuer", ()) if x)
	sans = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
	if cert:
		rep.add("Issued to: %s." % (subj.get("commonName") or (sans[0] if sans else "unknown")))
		rep.add("Issued by: %s." % (iss.get("organizationName") or iss.get("commonName") or "unknown"))
		if cert.get("subject") == cert.get("issuer"):
			rep.warn("The certificate is self-signed.", fix="Replace the self-signed certificate.")
		if sans:
			shown = ", ".join(sans[:8]) + (" and %d more" % (len(sans) - 8) if len(sans) > 8 else "")
			rep.add("Valid for %d name(s): %s." % (len(sans), shown))
			if not _covers(host, sans) and not re.match(r"^[\d.:]+$", host):
				rep.bad("The certificate does not list %s." % host, fix="Issue a certificate that includes %s." % host)
				lost += 10
		if cert.get("notAfter"):
			end = ssl.cert_time_to_seconds(cert["notAfter"])
			days = int((end - time.time()) // 86400)
			when = time.strftime("%Y-%m-%d", time.gmtime(end))
			if days < 0:
				rep.bad("The certificate expired %d days ago, on %s." % (-days, when), fix="Renew the expired certificate now.")
				lost += 20
			elif days < 14:
				rep.bad("The certificate expires in %d days, on %s." % (days, when), fix="Renew the certificate within days.")
				lost += 10
			elif days < 30:
				rep.warn("The certificate expires in %d days, on %s." % (days, when), fix="Renew the certificate soon.")
			else:
				rep.good("The certificate is valid for %d more days, until %s." % (days, when))
	rep.pen(min(lost, 20))


def _sec_headers(rep, fin):
	rep.h("Security headers", "web")
	H = fin["headers"]
	https = fin["url"].lower().startswith("https://")
	hsts = H.get("strict-transport-security", "")
	if not https:
		rep.warn("HSTS cannot work without HTTPS.", 15, "Serve the site over HTTPS, then add HSTS.")
	elif not hsts:
		rep.warn("No Strict-Transport-Security (HSTS) header. Browsers may still try plain HTTP first.", 15,
			"Add the Strict-Transport-Security header.")
	else:
		m = re.search(r"max-age=(\d+)", hsts, re.I)
		age = int(m.group(1)) if m else 0
		if age >= 15552000:
			extra = []
			if "includesubdomains" in hsts.lower():
				extra.append("covers subdomains")
			if "preload" in hsts.lower():
				extra.append("preload ready")
			rep.good("HSTS is on for %d days%s." % (age // 86400, (", " + ", ".join(extra)) if extra else ""))
		else:
			rep.warn("HSTS lasts only %d days. Use at least 180 days." % (age // 86400), 7, "Raise the HSTS max-age to at least 15552000.")
	csp = H.get("content-security-policy", "")
	if not csp:
		if "content-security-policy-report-only" in H:
			rep.warn("The Content-Security-Policy is in report-only mode, so nothing is blocked yet.", 14,
				"Switch the Content-Security-Policy from report-only to enforced.")
		else:
			rep.warn("No Content-Security-Policy. This header is the strongest defence against injected scripts.", 20,
				"Add a Content-Security-Policy header.")
	else:
		risky = [x for x in ("'unsafe-inline'", "'unsafe-eval'") if x in csp]
		if re.search(r"(?:script-src|default-src)[^;]*\s\*(?:\s|;|$)", csp):
			risky.append("a wildcard source")
		if risky:
			rep.warn("The Content-Security-Policy allows %s, which weakens it." % " and ".join(risky), 8,
				"Tighten the Content-Security-Policy (remove %s)." % ", ".join(risky))
		else:
			rep.good("A Content-Security-Policy is set and has no obviously unsafe rules.")
	if "nosniff" in H.get("x-content-type-options", "").lower():
		rep.good("X-Content-Type-Options is nosniff.")
	else:
		rep.warn("X-Content-Type-Options: nosniff is missing.", 8, "Add X-Content-Type-Options: nosniff.")
	if H.get("x-frame-options") or "frame-ancestors" in csp:
		rep.good("Clickjacking protection is set.")
	else:
		rep.warn("No clickjacking protection (X-Frame-Options or frame-ancestors).", 8, "Add X-Frame-Options or CSP frame-ancestors.")
	if H.get("referrer-policy"):
		rep.good("Referrer-Policy is %s." % H["referrer-policy"])
	else:
		rep.warn("No Referrer-Policy, so full page addresses may be passed to other sites.", 6, "Add a Referrer-Policy header.")
	if H.get("permissions-policy") or H.get("feature-policy"):
		rep.good("Permissions-Policy is set.")
	else:
		rep.warn("No Permissions-Policy to limit camera, microphone and location use.", 4, "Add a Permissions-Policy header.")
	if H.get("cross-origin-opener-policy") or H.get("cross-origin-resource-policy"):
		rep.good("Cross-origin isolation headers are set.")
	else:
		rep.add("Note: no Cross-Origin-Opener-Policy or Cross-Origin-Resource-Policy header (advanced hardening).")
		rep.pen(4)
	leaks = []
	for k in ("server", "x-powered-by", "x-aspnet-version", "x-aspnetmvc-version"):
		v = H.get(k, "")
		if v and (k != "server" or re.search(r"\d+\.\d+", v)):
			leaks.append("%s: %s" % (k, v))
	if leaks:
		rep.warn("The server reveals software details (%s). Attackers use this to find known weaknesses." % "; ".join(leaks), 5,
			"Hide software version headers.")
	else:
		rep.good("No software version is revealed in the headers.")
	if H.get("access-control-allow-origin") == "*":
		if H.get("access-control-allow-credentials", "").lower() == "true":
			rep.bad("CORS allows every site together with credentials.", fix="Fix the CORS policy.")
		else:
			rep.add("Note: CORS allows any site to read this response (normal for public data).")


def _sec_cookies(rep, fin):
	rep.h("Cookies", "web")
	cookies = fin["cookies"]
	if not cookies:
		rep.good("The page sets no cookies.")
		return
	https = fin["url"].lower().startswith("https://")
	weak, nosame = [], []
	for c in cookies:
		parts = [p.strip() for p in c.split(";")]
		name = parts[0].split("=")[0]
		attrs = [p.lower() for p in parts[1:]]
		secure = "secure" in attrs
		httponly = "httponly" in attrs
		samesite = any(a.startswith("samesite") for a in attrs)
		flags = ", ".join(x for x, on in (("Secure", secure), ("HttpOnly", httponly), ("SameSite", samesite)) if on)
		rep.add("Cookie %s: %s." % (name, flags or "no protection flags"))
		if (https and not secure) or not httponly:
			weak.append(name)
		if not samesite:
			nosame.append(name)
	if weak:
		rep.warn("These cookies lack Secure or HttpOnly: %s." % ", ".join(weak[:6]), 5,
			"Add Secure and HttpOnly to cookies: %s." % ", ".join(weak[:6]))
	elif nosame:
		rep.warn("These cookies have no SameSite setting: %s." % ", ".join(nosame[:6]), 1, "Add SameSite to cookies.")
	else:
		rep.good("All cookies have Secure, HttpOnly and SameSite.")


def _sec_speed(rep, pr, fin, trace):
	rep.h("Speed and size")
	if pr and "error" not in pr:
		rep.add("Looking up the address (DNS): %s." % _ms(pr["dns"]))
		rep.add("Opening the connection (TCP): %s." % _ms(pr["tcp"]))
		rep.add("Securing it (TLS handshake): %s." % _ms(pr["tls"]))
	rep.add("Connection setup in the page request: %s." % _ms(fin["connect"]))
	w = fin["wait"]
	msg = "Server wait before the first byte: %s." % _ms(w)
	if w < 0.2:
		rep.good(msg + " That is fast.")
	elif w < 0.6:
		rep.add(msg + " Acceptable.")
	else:
		rep.warn(msg + " That is slow.", fix="Speed up the server response (%s now)." % _ms(w))
	rep.add("Download time: %s." % _ms(fin["download"]))
	total = sum(h["connect"] + h["wait"] + h["download"] for h in trace["hops"])
	rep.add("Total time including redirects: %s." % _ms(total))
	rep.add("Page size: %s%s%s." % ("at least " if fin["truncated"] else "", _size(fin["size"]),
		(", %s on the wire" % _size(fin["wire"])) if fin["wire"] != fin["size"] else ""))
	ctype = fin["headers"].get("content-type", "").lower()
	if fin["encoding"]:
		rep.good("Compression is on (%s)." % fin["encoding"])
	elif ("text" in ctype or "json" in ctype) and fin["size"] > 1500:
		rep.warn("The page is not compressed. Gzip or Brotli would make it much smaller.", fix="Turn on gzip or Brotli compression.")
	if fin["size"] > 2 * 1048576:
		rep.warn("The page itself is very large (%s)." % _size(fin["size"]), fix="Reduce the page size.")
	cc = fin["headers"].get("cache-control")
	rep.add("Caching: %s." % (cc if cc else "no Cache-Control header" + (", but an ETag is sent" if fin["headers"].get("etag") else "")))


def _sec_tech(rep, fin, pr):
	rep.h("Technology and hosting clues")
	H = fin["headers"]
	found = [name for key, name in CDN_HEADERS if key in H]
	via = H.get("via")
	if H.get("server"):
		rep.add("Server software: %s." % H["server"])
	if H.get("x-powered-by"):
		rep.add("Powered by: %s." % H["x-powered-by"])
	m = re.search(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']([^\"']+)", fin["text"], re.I)
	if m:
		rep.add("Page generator: %s." % m.group(1))
	if found:
		rep.add("Platform or CDN detected: %s." % ", ".join(found))
	if via:
		rep.add("Passed through proxy: %s." % via)
	rep.add("HTTP version used by this check: %s." % ("1.1" if fin["version"] == 11 else "1.0"))
	if pr and pr.get("ips"):
		rep.add("Server address(es): %s." % ", ".join(pr["ips"][:6]))
		ip = pr["ips"][0]
		if ":" not in ip:
			try:
				d = http_json("http://ip-api.com/json/%s?fields=status,country,regionName,city,isp,org,as" % ip, timeout=8)
				if d.get("status") == "success":
					rep.add("Hosted by %s (%s) in %s, %s, %s." % (d.get("org") or d.get("isp"), d.get("as", ""), d.get("city"),
						d.get("regionName"), d.get("country")))
			except Exception:
				pass


def _sec_files(rep, base):
	rep.h("security.txt and robots.txt")
	for path, label in (("/.well-known/security.txt", "security.txt"), ("/robots.txt", "robots.txt")):
		try:
			h = _hop(base + path, limit=20000)
		except Exception:
			rep.add("%s: could not be checked." % label)
			continue
		ok = h["status"] == 200 and "html" not in h["headers"].get("content-type", "").lower()
		if label == "security.txt":
			if ok and re.search(r"^contact:", h["text"], re.I | re.M):
				rep.good("security.txt is published with a contact, so researchers know whom to tell about problems.")
			else:
				rep.add("Note: no security.txt found at /.well-known/security.txt (recommended).")
		else:
			rep.add("robots.txt: %s." % ("found (%d lines)" % len(h["text"].splitlines()) if ok else "not found"))


# ------------------------------------------------------------------ DNS and email
def _doh(name, rtype):
	return http_json("https://dns.google/resolve?name=%s&type=%s" % (quote(name), rtype), timeout=10,
		headers={"Accept": "application/dns-json"})


def _answers(name, rtype):
	try:
		return _doh(name, rtype).get("Answer") or []
	except Exception:
		return []


def _txt(name):
	out = []
	for a in _answers(name, "TXT"):
		d = a.get("data", "")
		parts = re.findall(r'"((?:[^"\\]|\\.)*)"', d)
		out.append("".join(parts) if parts else d.strip('"'))
	return out


def _zone(host):
	"""Walk up from the host name to the first name that has name servers (the registered domain or a zone)."""
	labels = host.split(".")
	for i in range(len(labels) - 1):
		name = ".".join(labels[i:])
		if any(a.get("type") == 2 for a in _answers(name, "NS")):
			return name
	return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _sec_dns(rep, host, zone):
	rep.h("DNS records for %s" % host)
	try:
		a = _doh(host, "A")
	except Exception as e:
		rep.add("DNS records could not be read (%s)." % e)
		return
	rows = [("A (IPv4)", "A"), ("AAAA (IPv6)", "AAAA"), ("CNAME (alias)", "CNAME")]
	for label, t in rows:
		data = a.get("Answer") if t == "A" else _answers(host, t)
		vals = [x["data"] for x in (data or []) if x.get("type") == {"A": 1, "AAAA": 28, "CNAME": 5}[t]]
		rep.add("%s: %s" % (label, ", ".join(vals[:6]) if vals else "none"))
	ns = [x["data"] for x in _answers(zone, "NS") if x.get("type") == 2]
	mx = [x["data"] for x in _answers(zone, "MX") if x.get("type") == 15]
	rep.add("Name servers of %s: %s" % (zone, ", ".join(ns[:6]) if ns else "none found"))
	rep.add("Mail servers (MX): %s" % (", ".join(m.rstrip(".") for m in mx[:6]) if mx else "none"))
	if not [x for x in (a.get("Answer") or []) if x.get("type") == 28]:
		rep.add("Note: the site has no IPv6 address, so people on IPv6-only networks may not reach it.")
	ad = a.get("AD")
	if ad:
		rep.good("DNSSEC validated: DNS answers cannot be forged on the way.")
	else:
		rep.add("DNSSEC: not validated for this name.")


def _sec_email(rep, zone):
	rep.h("Email security for %s" % zone, "mail")
	mx = [x["data"] for x in _answers(zone, "MX") if x.get("type") == 15]
	nullmx = bool(mx) and all(m.split()[-1] == "." for m in mx)
	if nullmx:
		rep.add("This domain declares that it does not receive email (null MX).")
	elif mx:
		rep.add("Mail servers: %s." % ", ".join(m.rstrip(".") for m in mx[:6]))
	else:
		rep.add("No MX records: the domain does not receive email.")
	receives = bool(mx) and not nullmx
	# SPF
	spf = [t for t in _txt(zone) if t.lower().startswith("v=spf1")]
	if not spf:
		rep.bad("No SPF record. Others can forge email from this domain more easily.", 30, "Publish an SPF record.")
	elif len(spf) > 1:
		rep.bad("There are %d SPF records. Only one is allowed, so receivers may ignore all of them." % len(spf), 25,
			"Merge the SPF records into one.")
	else:
		s = spf[0]
		rep.add("SPF record: %s" % s)
		m = re.search(r"(?:^|\s)([+\-~?]?)all(?:\s|$)", s)
		q = m.group(1) if m else None
		lookups = len(re.findall(r"(?:^|\s)[+\-~?]?(?:include|a|mx|ptr|exists)(?::|/|\s|$)", s)) + s.count("redirect=")
		if q is None:
			rep.warn("The SPF record has no 'all' ending, so unknown senders are not addressed.", 10, "End the SPF record with -all or ~all.")
		elif q == "-":
			rep.good("SPF ends with -all: only listed servers may send.")
		elif q == "~":
			rep.good("SPF ends with ~all (soft fail). Acceptable; -all is stricter.")
			rep.pen(3)
		elif q == "?":
			rep.warn("SPF ends with ?all, which gives no protection.", 20, "Change ?all to -all or ~all in SPF.")
		else:
			rep.bad("SPF ends with +all (or plain all): it allows anyone to send as this domain.", 30, "Change +all to -all in SPF.")
		if lookups > 10:
			rep.bad("SPF uses about %d DNS lookups directly, over the limit of 10, so it may fail." % lookups, 10, "Reduce SPF lookups below 10.")
		elif lookups > 8:
			rep.warn("SPF uses about %d lookups, close to the limit of 10 (included records add more)." % lookups, fix="Watch the SPF lookup count.")
		if "ptr" in s.lower().split():
			rep.warn("SPF uses the discouraged ptr mechanism.", fix="Remove ptr from SPF.")
	# DMARC
	dm = [t for t in _txt("_dmarc." + zone) if t.lower().startswith("v=dmarc1")]
	if not dm:
		rep.bad("No DMARC record. Receivers get no instruction on what to do with forged email, and you get no reports.", 40,
			"Publish a DMARC record (start with p=none and a rua address).")
	else:
		tags = {}
		for part in dm[0].split(";"):
			if "=" in part:
				k, v = part.split("=", 1)
				tags[k.strip().lower()] = v.strip()
		rep.add("DMARC record: %s" % dm[0])
		p = tags.get("p", "").lower()
		if p == "reject":
			rep.good("DMARC policy is reject: forged email is refused.")
		elif p == "quarantine":
			rep.good("DMARC policy is quarantine: forged email goes to spam. Reject is the strongest.")
			rep.pen(8)
		else:
			rep.warn("DMARC policy is none: it only monitors and blocks nothing.", 25, "Move DMARC from p=none to quarantine, then reject.")
		if tags.get("pct", "100") != "100":
			rep.warn("DMARC applies to only %s%% of email." % tags["pct"], 5, "Set DMARC pct to 100.")
		if "rua" not in tags:
			rep.warn("No DMARC rua address, so you receive no reports.", 3, "Add a DMARC rua address.")
	# DKIM
	def sel(s):
		return s, [t for t in _txt("%s._domainkey.%s" % (s, zone)) if "p=" in t.lower() or "v=dkim1" in t.lower()]
	with ThreadPoolExecutor(max_workers=6) as ex:
		found = [s for s, r in ex.map(sel, DKIM_SELECTORS) if r]
	if found:
		rep.good("DKIM keys found for selector(s): %s." % ", ".join(found))
	elif receives or spf:
		rep.warn("No DKIM key found among %d common selectors. Your provider may use a different selector name, so this is not proof." %
			len(DKIM_SELECTORS), 5, "Check that DKIM signing is set up.")
	# MTA-STS and TLS reporting
	if receives:
		if [t for t in _txt("_mta-sts." + zone) if t.lower().startswith("v=stsv1")]:
			rep.good("MTA-STS is published, so other servers must use encryption when sending you email.")
		else:
			rep.warn("No MTA-STS policy, so email to this domain can be downgraded to unencrypted delivery.", 5, "Publish MTA-STS.")
	# CAA and DNSSEC
	caa = [x["data"] for x in _answers(zone, "CAA") if x.get("type") == 257]
	if caa:
		rep.good("CAA records limit which authorities may issue certificates: %s." % "; ".join(caa[:4]))
	else:
		rep.warn("No CAA record, so any certificate authority may issue certificates for this domain.", 3, "Add a CAA record.")
	try:
		ad = _doh(zone, "SOA").get("AD")
	except Exception:
		ad = None
	if ad:
		rep.good("The domain is protected by DNSSEC.")
	else:
		rep.warn("DNSSEC is not enabled for the domain.", 3, "Enable DNSSEC.")


# ------------------------------------------------------------------ assembling the report
MODES = [
	"Full inspection (everything)",
	"Security headers and cookies",
	"Certificate and encryption",
	"Redirect trace",
	"Speed and timing breakdown",
	"Email domain security (SPF, DKIM, DMARC)",
	"DNS records overview",
]


def inspect(raw, mode):
	url, host, port, explicit = _target(raw)
	rep = _Report()
	pr = fin = tr = None
	start = url
	if mode == 3 and not explicit:
		start = "http://%s/" % host
	if mode in (0, 1, 3, 4):
		tr = _trace(start)
		fin = tr["hops"][-1]
	if mode in (0, 2, 4):
		try:
			pr = _probe(host, port if url.lower().startswith("https") else 443)
		except Exception as e:
			pr = {"error": str(e)}
	final_https = bool(fin and fin["url"].lower().startswith("https://")) or (fin is None and pr is not None and "error" not in pr)
	zone = None
	if mode in (0, 5, 6):
		zone = _zone(host[4:] if host.startswith("www.") and mode == 5 else host)

	if mode in (0, 3):
		_sec_redirects(rep, tr, start, explicit)
	if mode in (0, 1) and urlparse(start).scheme == "https" and port == 443:
		_sec_http_upgrade(rep, host)
	if mode in (0, 2):
		_sec_tls(rep, pr, "https" if final_https else "http", host)
	if mode in (0, 1):
		_sec_headers(rep, fin)
		_sec_cookies(rep, fin)
	if mode in (0, 4):
		_sec_speed(rep, pr, fin, tr)
	if mode == 0:
		_sec_tech(rep, fin, pr)
		_sec_files(rep, "%s://%s" % (urlparse(fin["url"]).scheme, urlparse(fin["url"]).netloc))
	if mode in (0, 6):
		_sec_dns(rep, host, zone)
	if mode in (0, 5):
		_sec_email(rep, zone)

	head = ["WEBSITE INSPECTOR", "Checked: %s" % raw.strip()]
	if fin and fin["url"].rstrip("/") != url.rstrip("/"):
		head.append("Final address: %s" % fin["url"])
	for group, label in (("web", "Website security score"),
		("mail", "Email security score")):
		if group in rep.lost and mode != 2:
			sc = rep.score(group)
			head.append("%s: %d out of 100, grade %s (an estimate based on common best practice)." % (label, sc, _grade(sc)))
	order = {"Problem": 0, "Warning": 1}
	issues = sorted(rep.issues, key=lambda x: order[x[0]])
	if rep.issues:
		head += ["", "FIX FIRST (%d problem(s), %d warning(s))" % (sum(1 for i in issues if i[0] == "Problem"),
			sum(1 for i in issues if i[0] == "Warning"))]
		head += ["%d. %s: %s" % (n, lvl, txt) for n, (lvl, txt) in enumerate(issues[:12], 1)]
		if len(issues) > 12:
			head.append("...and %d more, listed in the details below." % (len(issues) - 12))
	elif rep.lost:
		head += ["", "No problems or warnings were found."]
	return "\n".join(head + [""] + rep.lines)


def tool_inspector():
	r = ask_form(_("Website inspector"), [
		{"key": "mode", "label": _("&What do you want to check?"), "type": "combo", "choices": [_(m) for m in MODES]},
		{"key": "url", "label": _("&Web address or domain (for example example.com):"), "type": "text", "required": True},
	], intro=_("Checks security, certificate, speed, DNS and email protection of any website. Nothing is installed or changed on the site."))
	if not r:
		return
	mode, raw = r["mode_index"], r["url"]

	def work():
		try:
			return inspect(raw, mode)
		except ValueError as e:
			return _("Error: %s") % e
		except ssl.SSLError as e:
			return _("Error: %s") % ("Secure connection failed: %s" % e)
		except socket.gaierror:
			return _("Error: %s") % "That address could not be found. Check the spelling."
		except (socket.timeout, TimeoutError):
			return _("Error: %s") % "The site did not answer in time."
		except OSError as e:
			return _("Error: %s") % ("Could not connect to the site (%s)." % e)
	run_async(work, _("Website inspector"))

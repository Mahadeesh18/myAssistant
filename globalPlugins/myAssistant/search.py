# -*- coding: UTF-8 -*-
"""Forgiving search for the tools list. Spelling mistakes still find the right tools.

Pure Python (no NVDA imports). Every word the user types is compared with every word of a
tool's name and category. A word matches when it is a prefix, a substring, sounds alike, or
is spelled almost the same (difflib). A tool is listed when all typed words match something.
"""
import difflib
import functools
import re

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"a", "an", "the", "to", "of", "and", "or", "for", "in", "on", "with", "from", "into", "my"}

# Related ideas: typing the left word also finds tools that talk about the right words.
SYNONYMS = {
	"calendar": ["date", "hijri", "alarm", "holidays"], "schedule": ["alarm", "timer", "date"],
	"reminder": ["alarm", "timer"], "clock": ["time", "alarm", "world"], "timezone": ["world", "clock", "time"],
	"time": ["clock", "alarm", "world"], "translate": ["translator", "language", "morse"],
	"language": ["translate", "words", "dictionary"], "mail": ["email", "write", "letter"],
	"email": ["write", "letter", "reply"], "cv": ["resume", "cover", "job", "interview"],
	"resume": ["cv", "cover", "job", "interview"], "job": ["interview", "cover", "resume"],
	"money": ["currency", "crypto", "calculator"], "exchange": ["currency", "crypto"],
	"price": ["crypto", "currency"], "bitcoin": ["crypto", "cryptocurrency"], "forecast": ["weather", "rain"],
	"rain": ["weather", "forecast"], "temperature": ["weather", "forecast"], "wifi": ["network", "internet", "speed"],
	"network": ["internet", "wifi", "ip", "dns"], "internet": ["network", "speed", "website"],
	"website": ["web", "page", "site", "url"], "web": ["page", "site", "website"], "link": ["url", "shorten", "web"],
	"password": ["breach", "generator", "security"], "security": ["password", "breach"],
	"battery": ["power", "system"], "computer": ["system", "power", "window"], "sound": ["volume", "effects"],
	"audio": ["volume", "sound"], "music": ["podcast", "sound"], "video": ["tv", "show"],
	"movie": ["tv", "show"], "news": ["headlines", "rss", "hacker"], "study": ["quiz", "trivia", "learn", "explain"],
	"quiz": ["trivia", "study"], "game": ["trivia", "quiz", "random", "dice"], "dice": ["random", "coin"],
	"random": ["dice", "coin", "joke", "fact"], "fun": ["joke", "trivia", "random", "fact"],
	"food": ["recipe", "nutrition", "product"], "cook": ["recipe"], "diet": ["recipe", "nutrition", "food"],
	"book": ["books", "library", "search"], "poem": ["poetry", "write"], "code": ["program", "python", "github"],
	"programming": ["code", "github", "package"], "map": ["location", "postal", "country"],
	"address": ["postal", "location", "zip"], "zip": ["postal", "code"], "postcode": ["postal", "zip"],
	"anime": ["manga", "tv", "show"], "space": ["station", "nasa", "rocket", "astronomy"],
	"nasa": ["space", "astronomy", "picture"], "star": ["space", "astronomy"], "text": ["clipboard", "words", "write"],
	"copy": ["clipboard"], "paste": ["clipboard"], "math": ["calculator", "convert"], "convert": ["converter", "calculator"],
	"unit": ["converter", "calculator"], "age": ["date", "calculator"], "prayer": ["salah", "namaz", "times"],
	"help": ["about", "tutorials"],
	"inspector": ["website", "security", "certificate", "dns", "email"], "ssl": ["certificate", "inspector", "website"],
	"tls": ["certificate", "inspector"], "https": ["certificate", "inspector", "website"],
	"certificate": ["inspector", "website", "security"], "headers": ["inspector", "security", "website"],
	"spf": ["inspector", "email"], "dmarc": ["inspector", "email"], "dkim": ["inspector", "email"],
	"audit": ["inspector", "analyzer", "website"], "hack": ["security", "inspector"], "settings": ["sound", "about"],
	"voice": ["gemini", "speech", "live", "voices"], "speech": ["gemini", "voices", "speak"], "tts": ["gemini", "speech", "voices"],
	"speak": ["gemini", "speech", "voices", "live"], "talk": ["live", "gemini", "assistant", "conversation"],
	"live": ["gemini", "assistant", "conversation"], "conversation": ["live", "gemini", "chat"],
	"screen": ["live", "gemini", "assistant", "image", "describer"], "gemini": ["voices", "live", "assistant", "search", "image", "document", "audio", "youtube"],
	"image": ["gemini", "describer", "screen", "picture"], "picture": ["image", "describer", "gemini"], "photo": ["image", "describer"],
	"ocr": ["image", "describer", "text"], "pdf": ["document", "reader", "gemini"], "document": ["pdf", "reader", "gemini"],
	"transcribe": ["audio", "transcriber", "video"], "transcript": ["audio", "transcriber"], "youtube": ["summarizer", "video", "web"],
	"summarize": ["summarizer", "summary", "gemini"], "describe": ["describer", "image", "screen"], "search": ["web", "gemini", "sources"],
}
_SYN_KEYS = list(SYNONYMS)


def _norm(s):
	return (s or "").lower()


def words(text):
	return _WORD.findall(_norm(text))


def _content_words(text):
	ws = words(text)
	keep = [w for w in ws if w not in _STOP]
	return keep or ws


def _synonyms_for(q):
	"""Related words for q. A near-miss spelling of a known word (emial) also gives that word back."""
	if q in SYNONYMS:
		return SYNONYMS[q]
	if len(q) >= 4:
		m = max(_SYN_KEYS, key=lambda k: _edit_sim(q, k))
		if _edit_sim(q, m) >= 0.78:
			return [m] + SYNONYMS[m]
	return []


def _edit_sim(a, b):
	"""1 minus the edit distance share. A swapped pair of letters (emial/email) counts as one edit."""
	la, lb = len(a), len(b)
	if abs(la - lb) > 2:
		return 0.0
	d = [[0] * (lb + 1) for _ in range(la + 1)]
	for i in range(la + 1):
		d[i][0] = i
	for j in range(lb + 1):
		d[0][j] = j
	for i in range(1, la + 1):
		for j in range(1, lb + 1):
			c = 0 if a[i - 1] == b[j - 1] else 1
			d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
			if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
				d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
	return 1.0 - d[la][lb] / max(la, lb)


def _skeleton(w):
	"""Rough sound-alike key: drop vowels after the first letter and squeeze repeats (calender -> clndr)."""
	if not w:
		return w
	w = w.replace("ph", "f").replace("ck", "k").replace("kn", "n").replace("wr", "r")
	out = [w[0]]
	for ch in w[1:]:
		if ch in "aeiouyhw":
			continue
		if ch == out[-1]:
			continue
		out.append(ch)
	return "".join(out)


@functools.lru_cache(maxsize=50000)
def word_score(q, w):
	"""How well the typed word q matches the tool word w, from 0 to 1."""
	if not q or not w:
		return 0.0
	if q == w:
		return 1.0
	if w.startswith(q):
		return 0.95 if len(q) >= 2 else 0.85
	if len(q) >= 3 and q in w:
		return 0.85
	best = 0.0
	if len(q) >= 3:
		# Compare against the start of the word too, so "calcul" and "calclator" both reach "calculator".
		r_full = difflib.SequenceMatcher(None, q, w).ratio()
		if len(w) < len(q) - 1:
			r_full *= len(w) / len(q)  # a much shorter word is rarely what was meant
		r_head = difflib.SequenceMatcher(None, q, w[:len(q) + 1]).ratio() if len(w) >= len(q) else 0.0
		best = max(r_full, r_head * 0.92, _edit_sim(q, w) * 0.97)
		if _skeleton(q) == _skeleton(w) and len(_skeleton(q)) >= 2:
			best = max(best, 0.82)
		elif len(q) >= 4 and _skeleton(w).startswith(_skeleton(q)) and len(_skeleton(q)) >= 3:
			best = max(best, 0.78)
	else:
		# Two letters: allow one typo only against a word of the same short length.
		if len(w) <= 3:
			best = difflib.SequenceMatcher(None, q, w).ratio() * 0.8
	return best


# Typed words must reach this score; longer words may be a little sloppier.
def _threshold(q, relax=0.0):
	t = 0.8 if len(q) <= 3 else 0.72
	return t - relax


def _best(q, tw, compact, relax):
	"""Score of typed word q against the tool words tw (and the joined name, for 'wifi' vs 'Wi-Fi').

	Returns 0 when it does not match. A related word (synonym) only counts when the tool really
	contains that word, and ranks below a direct match."""
	best = max(word_score(q, w) for w in tw)
	if len(q) >= 4 and q in compact:
		best = max(best, 0.88)
	if best >= _threshold(q, relax):
		return best
	syn_best = 0.0
	for syn in _synonyms_for(q):
		syn_best = max(syn_best, max(word_score(syn, w) for w in tw))
	return syn_best * 0.7 if syn_best >= 0.9 else 0.0


def score_item(query_words, text, relax=0.0):
	"""Score of one tool for the typed words (0 means it does not match)."""
	tw = _content_words(text)
	if not tw:
		return 0.0
	compact = "".join(words(text))
	total = 0.0
	for q in query_words:
		best = _best(q, tw, compact, relax)
		if best <= 0.0:
			return 0.0
		total += best
	# Prefer tools whose name starts with the first typed word, then shorter, more specific names.
	bonus = 0.05 if tw[0].startswith(query_words[0][:3]) else 0.0
	return total / len(query_words) + bonus - min(len(tw), 12) * 0.002


def _rank(qw, items, category_of, relax):
	scored = []
	for idx, it in enumerate(items):
		name = it[0]
		s = score_item(qw, name, relax)
		if category_of:
			cat = category_of(it)
			if cat:
				s = max(s, score_item(qw, name + " " + cat, relax) * 0.9)
		if s > 0:
			scored.append((-s, idx, it))
	scored.sort(key=lambda t: (t[0], t[1]))
	return [it for _s, _i, it in scored]


def filter_tools(query, items, category_of=None):
	"""items: list of (name, function). Returns the matching items, best match first.

	category_of: optional function item -> category name, searched together with the tool name
	(with a lower weight, so typing 'internet' also lists the internet tools).
	An empty query returns all items unchanged. When nothing matches closely, a looser
	second pass lists the most related tools instead of an empty list.
	"""
	qw = [w for w in words(query) if w not in _STOP] or words(query)
	if not qw:
		return list(items)
	res = _rank(qw, items, category_of, 0.0)
	if not res:
		res = _rank(qw, items, category_of, 0.1)[:10]
	return res

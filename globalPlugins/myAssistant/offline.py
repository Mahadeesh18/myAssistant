# -*- coding: UTF-8 -*-
"""10 offline tools. Every result is shown in a dialog."""
import calendar
import datetime
import math
import re
from collections import Counter
import addonHandler
from .common import speak, ask_text, ask_number, choose, show_text, _clip, ask_form, ask_date_combo

addonHandler.initTranslation()

TITLE_UNIT = "Unit converter"

# ---------------------------------------------------------------- 1. unit converter
UNITS = {
	"Length": [("millimeters", 0.001), ("centimeters", 0.01), ("meters", 1), ("kilometers", 1000),
		("inches", 0.0254), ("feet", 0.3048), ("yards", 0.9144), ("miles", 1609.344)],
	"Weight": [("milligrams", 1e-6), ("grams", 0.001), ("kilograms", 1), ("tonnes", 1000),
		("ounces", 0.028349523125), ("pounds", 0.45359237), ("stone", 6.35029318)],
	"Volume": [("milliliters", 0.001), ("liters", 1), ("US teaspoons", 0.00492892159375),
		("US tablespoons", 0.01478676478125), ("US fluid ounces", 0.0295735295625), ("US cups", 0.2365882365),
		("US quarts", 0.946352946), ("US gallons", 3.785411784)],
	"Speed": [("meters per second", 1), ("kilometers per hour", 1 / 3.6), ("miles per hour", 0.44704),
		("knots", 1852 / 3600)],
	"Area": [("square meters", 1), ("square kilometers", 1e6), ("hectares", 1e4), ("acres", 4046.8564224),
		("square feet", 0.09290304), ("square miles", 2589988.110336)],
	"Digital storage": [("bytes", 1), ("kilobytes", 1024), ("megabytes", 1024 ** 2), ("gigabytes", 1024 ** 3),
		("terabytes", 1024 ** 4)],
	"Time": [("seconds", 1), ("minutes", 60), ("hours", 3600), ("days", 86400), ("weeks", 604800)],
	"Temperature": [("Celsius", None), ("Fahrenheit", None), ("Kelvin", None)],
}


def convert_units(cat, i, j, v):
	units = UNITS[cat]
	if cat == "Temperature":
		c = (v, (v - 32) * 5 / 9, v - 273.15)[i]
		return (c, c * 9 / 5 + 32, c + 273.15)[j]
	return v * units[i][1] / units[j][1]


def tool_units():
	cats = list(UNITS)
	c = choose(_("Category:"), _(TITLE_UNIT), [_(x) for x in cats])
	if c < 0:
		return
	cat = cats[c]
	names = [_(u[0]) for u in UNITS[cat]]
	i = choose(_("Convert from:"), _(TITLE_UNIT), names)
	if i < 0:
		return
	j = choose(_("Convert to:"), _(TITLE_UNIT), names)
	if j < 0:
		return
	v = ask_number(_("Value in %s:") % names[i], _(TITLE_UNIT), "1")
	if v is None:
		return
	r = convert_units(cat, i, j, v)
	show_text(_(TITLE_UNIT), "%s %s = %s %s" % (_fmtnum(v), names[i], _fmtnum(r), names[j]))


def _fmtnum(x):
	if x == int(x) and abs(x) < 1e15:
		return "{:,}".format(int(x))
	return "{:,.6f}".format(x).rstrip("0").rstrip(".")


# ---------------------------------------------------------------- dates
def parse_date(s):
	s = s.strip()
	for f in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y"):
		try:
			return datetime.datetime.strptime(s, f).date()
		except ValueError:
			pass
	return None


def ask_date(prompt, title, default=""):
	"""Year, month and day combo boxes instead of typing a date. default is an ISO date string or empty."""
	d = parse_date(default) if default else None
	return ask_date_combo(title, prompt, d or datetime.date.today())


def _add_months(d, n):
	t = d.year * 12 + d.month - 1 + n
	y, m = t // 12, t % 12 + 1
	return datetime.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def ymd_diff(a, b):
	"""Years, months, days from date a to date b (a <= b)."""
	months = (b.year - a.year) * 12 + b.month - a.month
	if _add_months(a, months) > b:
		months -= 1
	return months // 12, months % 12, (b - _add_months(a, months)).days


def next_birthday(born, today):
	for yr in (today.year, today.year + 1):
		day = min(born.day, calendar.monthrange(yr, born.month)[1])
		nb = datetime.date(yr, born.month, day)
		if nb >= today:
			return nb


# 2
def age_report(born, today):
	y, m, d = ymd_diff(born, today)
	nb = next_birthday(born, today)
	days = (today - born).days
	return ("Born: %s\nAge: %d years, %d months, %d days\nTotal: %s days, about %s weeks, about %s months\n"
		"Next birthday: %s, in %d days (turning %d)") % (
		born.strftime("%A %d %B %Y"), y, m, d, "{:,}".format(days), "{:,}".format(days // 7),
		"{:,}".format(y * 12 + m), nb.strftime("%A %d %B %Y"), (nb - today).days, nb.year - born.year)


def tool_age():
	born = ask_date(_("Choose your date of birth:"), _("Age calculator"), "2000-01-01")
	if not born:
		return
	today = datetime.date.today()
	if born > today:
		show_text(_("Age calculator"), _("That date is in the future."))
		return
	show_text(_("Age calculator"), age_report(born, today))


# 3
def tool_datecalc():
	i = choose(_("Choose:"), _("Date calculator"), [_("Days between two dates"), _("Add or subtract days from a date")])
	if i < 0:
		return
	today = datetime.date.today()
	if i == 0:
		a = ask_date(_("Choose the first date:"), _("Date calculator"), today.isoformat())
		if not a:
			return
		b = ask_date(_("Choose the second date:"), _("Date calculator"), today.isoformat())
		if not b:
			return
		lo, hi = sorted((a, b))
		y, m, d = ymd_diff(lo, hi)
		n = (hi - lo).days
		show_text(_("Date calculator"), "From %s to %s\n%s days (%d weeks and %d days)\n%d years, %d months, %d days" % (
			lo.strftime("%A %d %B %Y"), hi.strftime("%A %d %B %Y"), "{:,}".format(n), n // 7, n % 7, y, m, d))
	else:
		a = ask_date(_("Choose the start date:"), _("Date calculator"), today.isoformat())
		if not a:
			return
		n = ask_number(_("Days to add (use a minus sign to subtract):"), _("Date calculator"), "30")
		if n is None:
			return
		try:
			r = a + datetime.timedelta(days=int(n))
		except OverflowError:
			speak(_("Date out of range"))
			return
		show_text(_("Date calculator"), "%s %+d days = %s" % (a.strftime("%A %d %B %Y"), int(n), r.strftime("%A %d %B %Y")))


# ---------------------------------------------------------------- 4. Hijri converter (tabular calendar, may differ by a day)
HIJRI_MONTHS = ["Muharram", "Safar", "Rabi al-Awwal", "Rabi al-Thani", "Jumada al-Awwal", "Jumada al-Thani",
	"Rajab", "Shaban", "Ramadan", "Shawwal", "Dhu al-Qadah", "Dhu al-Hijjah"]


def gregorian_to_hijri(d):
	jd = d.toordinal() + 1721425
	l = jd - 1948440 + 10632
	n = (l - 1) // 10631
	l = l - 10631 * n + 354
	j = ((10985 - l) // 5316) * ((50 * l) // 17719) + (l // 5670) * ((43 * l) // 15238)
	l = l - ((30 - j) // 15) * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
	m = (24 * l) // 709
	day = l - (709 * m) // 24
	return 30 * n + j - 30, m, day


def hijri_to_gregorian(y, m, d):
	jd = (11 * y + 3) // 30 + 354 * y + 30 * m - (m - 1) // 2 + d + 1948440 - 385
	return datetime.date.fromordinal(jd - 1721425)


def tool_hijri():
	i = choose(_("Choose:"), _("Hijri date converter"),
		[_("Today in Hijri"), _("Gregorian date to Hijri"), _("Hijri date to Gregorian")])
	if i < 0:
		return
	note = "\n" + _("Calculated with the tabular Islamic calendar. The moon-sighting date may differ by one day.")
	if i in (0, 1):
		g = datetime.date.today()
		if i == 1:
			g = ask_date(_("Choose the Gregorian date:"), _("Hijri date converter"), g.isoformat())
			if not g:
				return
		y, m, d = gregorian_to_hijri(g)
		show_text(_("Hijri date converter"), "%s = %d %s %d AH%s" % (g.strftime("%A %d %B %Y"), d, HIJRI_MONTHS[m - 1], y, note))
	else:
		ty, tm, td = gregorian_to_hijri(datetime.date.today())
		res = ask_date_combo(_("Hijri date converter"), _("Choose the Hijri date:"), (ty, tm, td), 1300, 1600,
			names=HIJRI_MONTHS, days=30)
		if not res:
			return
		y, mo, d = res
		g = hijri_to_gregorian(y, mo, d)
		show_text(_("Hijri date converter"), "%d %s %d AH = %s%s" % (d, HIJRI_MONTHS[mo - 1], y, g.strftime("%A %d %B %Y"), note))


# ---------------------------------------------------------------- 5. text statistics
def text_stats(t):
	words = re.findall(r"\b[\w'’-]+\b", t)
	sentences = [s for s in re.split(r"[.!?]+(?:\s|$)", t) if s.strip()]
	paras = [p for p in re.split(r"\n\s*\n", t) if p.strip()]
	common = Counter(w.lower() for w in words if len(w) > 3).most_common(5)
	nw = len(words)
	return ("Characters: %s (%s without spaces)\nWords: %s\nSentences: %d\nLines: %d\nParagraphs: %d\n"
		"Average word length: %.1f letters\nReading time: about %.1f minutes\nSpeaking time: about %.1f minutes\n"
		"Most used words: %s") % ("{:,}".format(len(t)), "{:,}".format(len(re.sub(r"\s", "", t))), "{:,}".format(nw),
		len(sentences), len(t.splitlines()), len(paras), (sum(len(w) for w in words) / nw) if nw else 0,
		nw / 200, nw / 130, ", ".join("%s (%d)" % c for c in common) or "none")


def tool_textstats():
	t = _clip()
	if t:
		show_text(_("Clipboard text statistics"), text_stats(t))


# ---------------------------------------------------------------- 6. text transformer
def _sentence_case(t):
	return re.sub(r"(^\s*|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t.lower())


TRANSFORMS = [
	("UPPERCASE", lambda t: t.upper()),
	("lowercase", lambda t: t.lower()),
	("Title Case", lambda t: t.title()),
	("Sentence case", _sentence_case),
	("Reverse the text", lambda t: t[::-1]),
	("Remove extra spaces and blank lines", lambda t: "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in t.splitlines() if l.strip())),
	("Sort lines A to Z", lambda t: "\n".join(sorted(t.splitlines(), key=str.lower))),
	("Remove duplicate lines", lambda t: "\n".join(dict.fromkeys(t.splitlines()))),
	("Number the lines", lambda t: "\n".join("%d. %s" % (i, l) for i, l in enumerate(t.splitlines(), 1))),
	("Join lines into one line", lambda t: " ".join(l.strip() for l in t.splitlines() if l.strip())),
]


def tool_texttransform():
	t = _clip()
	if not t:
		return
	i = choose(_("Transform the clipboard text:"), _("Text transformer"), [_(n) for n, _f in TRANSFORMS])
	if i >= 0:
		show_text(_("Text transformer"), TRANSFORMS[i][1](t))


# ---------------------------------------------------------------- 7. number base converter
ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
	(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def to_roman(n):
	out = ""
	for v, s in ROMAN:
		while n >= v:
			out += s
			n -= v
	return out


def from_roman(s):
	s = s.upper().strip()
	if not s or not re.match(r"^[MDCLXVI]+$", s):
		raise ValueError
	n, i = 0, 0
	for v, r in ROMAN:
		while s.startswith(r, i):
			n += v
			i += len(r)
	if i != len(s) or to_roman(n) != s:
		raise ValueError
	return n


BASES = [("Decimal", 10), ("Binary", 2), ("Octal", 8), ("Hexadecimal", 16), ("Roman numeral", 0)]


def base_report(text, kind):
	n = from_roman(text) if kind == 0 else int(text.strip().replace(" ", "").replace(",", ""), kind)
	out = ["Decimal: %s" % "{:,}".format(n), "Binary: %s" % bin(n)[2:] if n >= 0 else "Binary: -%s" % bin(-n)[2:],
		"Octal: %s" % oct(abs(n))[2:], "Hexadecimal: %s" % hex(abs(n))[2:].upper()]
	if 0 < n < 4000:
		out.append("Roman numeral: %s" % to_roman(n))
	return "\n".join(out)


def tool_base():
	i = choose(_("Your number is in:"), _("Number base converter"), [_(n) for n, _b in BASES])
	if i < 0:
		return
	s = ask_text(_("Enter the number:"), _("Number base converter"))
	if not s:
		return
	try:
		show_text(_("Number base converter"), base_report(s, BASES[i][1]))
	except ValueError:
		speak(_("That is not a valid number in the chosen system"))


# ---------------------------------------------------------------- 8. Morse code
MORSE = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....", "I": "..",
	"J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
	"S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..",
	"0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
	"8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--",
	"/": "-..-.", "(": "-.--.", ")": "-.--.-", "&": ".-...", ":": "---...", ";": "-.-.-.", "=": "-...-",
	"+": ".-.-.", "-": "-....-", "_": "..--.-", '"': ".-..-.", "$": "...-..-", "@": ".--.-."}
MORSE_REV = {v: k for k, v in MORSE.items()}


def morse_encode(t):
	words = []
	for w in t.upper().split():
		words.append(" ".join(MORSE[c] for c in w if c in MORSE))
	return " / ".join(words)


def morse_decode(t):
	t = t.replace("_", "-").replace("•", ".").replace("−", "-")
	out = []
	for w in re.split(r"\s*/\s*|\s{3,}", t.strip()):
		out.append("".join(MORSE_REV.get(c, "?") for c in w.split()))
	return " ".join(out)


def tool_morse():
	i = choose(_("Choose:"), _("Morse code"), [_("Text to Morse code"), _("Morse code to text")])
	if i < 0:
		return
	s = ask_text(_("Enter the text:") if i == 0 else _("Enter Morse code (dots and dashes, letters separated by spaces, words by a slash):"),
		_("Morse code"), multiline=True)
	if s:
		show_text(_("Morse code"), morse_encode(s) if i == 0 else morse_decode(s))


# ---------------------------------------------------------------- 9. percentage calculator
def percent(mode, x, y):
	if mode == 0:
		return "%s%% of %s = %s" % (_fmtnum(x), _fmtnum(y), _fmtnum(x / 100 * y))
	if mode == 1:
		if y == 0:
			raise ZeroDivisionError
		return "%s is %s%% of %s" % (_fmtnum(x), _fmtnum(round(x / y * 100, 6)), _fmtnum(y))
	if mode == 2:
		return "%s increased by %s%% = %s" % (_fmtnum(y), _fmtnum(x), _fmtnum(round(y * (1 + x / 100), 6)))
	if mode == 3:
		return "%s decreased by %s%% = %s" % (_fmtnum(y), _fmtnum(x), _fmtnum(round(y * (1 - x / 100), 6)))
	if x == 0:
		raise ZeroDivisionError
	ch = (y - x) / abs(x) * 100
	return "Change from %s to %s = %s%% (%s)" % (_fmtnum(x), _fmtnum(y), _fmtnum(round(ch, 6)),
		"increase" if ch > 0 else ("decrease" if ch < 0 else "no change"))


PERCENT_MODES = [("What is X percent of Y", "Percent (X):", "Number (Y):"),
	("X is what percent of Y", "Number (X):", "Total (Y):"),
	("Increase Y by X percent", "Percent (X):", "Number (Y):"),
	("Decrease Y by X percent (discount)", "Percent (X):", "Number (Y):"),
	("Percentage change from X to Y", "Old value (X):", "New value (Y):")]


def tool_percent():
	i = choose(_("Choose a calculation:"), _("Percentage calculator"), [_(m[0]) for m in PERCENT_MODES])
	if i < 0:
		return
	x = ask_number(_(PERCENT_MODES[i][1]), _("Percentage calculator"))
	if x is None:
		return
	y = ask_number(_(PERCENT_MODES[i][2]), _("Percentage calculator"))
	if y is None:
		return
	try:
		show_text(_("Percentage calculator"), percent(i, x, y))
	except ZeroDivisionError:
		show_text(_("Percentage calculator"), _("Cannot divide by zero"))


# ---------------------------------------------------------------- 10. loan / EMI calculator
def emi(principal, annual_rate, months):
	r = annual_rate / 1200
	pay = principal / months if r == 0 else principal * r * (1 + r) ** months / ((1 + r) ** months - 1)
	return pay, pay * months, pay * months - principal


def _check_loan(v):
	try:
		if float(v["p"]) <= 0:
			return _("The loan amount must be more than zero.")
		if float(v["r"]) < 0:
			return _("The interest rate cannot be negative.")
		if int(float(v["m"])) < 1:
			return _("The loan term must be at least one month.")
	except ValueError:
		return _("The interest rate and loan term must be numbers.")
	return None


def tool_loan():
	r = ask_form(_("Loan calculator"), [
		{"key": "p", "label": _("Loan &amount:"), "type": "number"},
		{"key": "r", "label": _("&Yearly interest rate in percent:"), "type": "editable",
			"choices": ["0", "3", "5", "7", "8", "10", "12", "15", "18", "20", "24"], "default": "10"},
		{"key": "m", "label": _("Loan &term in months:"), "type": "editable",
			"choices": ["6", "12", "18", "24", "36", "48", "60", "84", "120", "180", "240", "300", "360"], "default": "12"},
	], validate=_check_loan)
	if not r:
		return
	p, rate, m = r["p"], float(r["r"]), int(float(r["m"]))
	pay, total, interest = emi(p, rate, m)
	show_text(_("Loan calculator"), "Loan %s at %s%% a year for %d months (%.1f years)\nMonthly payment: %s\n"
		"Total to repay: %s\nTotal interest: %s" % (_fmtnum(p), _fmtnum(rate), m, m / 12, "{:,.2f}".format(pay),
		"{:,.2f}".format(total), "{:,.2f}".format(interest)))


OFFLINE_TOOLS = [
	(_("Unit converter"), tool_units),
	(_("Age calculator"), tool_age),
	(_("Date calculator"), tool_datecalc),
	(_("Hijri and Gregorian date converter"), tool_hijri),
	(_("Clipboard text statistics"), tool_textstats),
	(_("Clipboard text transformer"), tool_texttransform),
	(_("Number base and Roman numeral converter"), tool_base),
	(_("Morse code translator"), tool_morse),
	(_("Percentage calculator"), tool_percent),
	(_("Loan and monthly payment calculator"), tool_loan),
]

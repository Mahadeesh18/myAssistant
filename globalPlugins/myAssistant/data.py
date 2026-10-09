# -*- coding: UTF-8 -*-
"""Ready-made lists used by the combo boxes, so the user never has to type codes or names."""

CURRENCIES = [
	("USD", "US Dollar"), ("EUR", "Euro"), ("GBP", "British Pound"), ("INR", "Indian Rupee"),
	("PKR", "Pakistani Rupee"), ("BDT", "Bangladeshi Taka"), ("LKR", "Sri Lankan Rupee"),
	("NPR", "Nepalese Rupee"), ("AED", "UAE Dirham"), ("SAR", "Saudi Riyal"), ("QAR", "Qatari Riyal"),
	("KWD", "Kuwaiti Dinar"), ("BHD", "Bahraini Dinar"), ("OMR", "Omani Rial"), ("JOD", "Jordanian Dinar"),
	("EGP", "Egyptian Pound"), ("TRY", "Turkish Lira"), ("ILS", "Israeli Shekel"), ("IRR", "Iranian Rial"),
	("IQD", "Iraqi Dinar"), ("AFN", "Afghan Afghani"), ("CNY", "Chinese Yuan"), ("JPY", "Japanese Yen"),
	("KRW", "South Korean Won"), ("HKD", "Hong Kong Dollar"), ("SGD", "Singapore Dollar"),
	("MYR", "Malaysian Ringgit"), ("IDR", "Indonesian Rupiah"), ("THB", "Thai Baht"),
	("PHP", "Philippine Peso"), ("VND", "Vietnamese Dong"), ("AUD", "Australian Dollar"),
	("NZD", "New Zealand Dollar"), ("CAD", "Canadian Dollar"), ("MXN", "Mexican Peso"),
	("BRL", "Brazilian Real"), ("ARS", "Argentine Peso"), ("CLP", "Chilean Peso"), ("COP", "Colombian Peso"),
	("CHF", "Swiss Franc"), ("SEK", "Swedish Krona"), ("NOK", "Norwegian Krone"), ("DKK", "Danish Krone"),
	("PLN", "Polish Zloty"), ("CZK", "Czech Koruna"), ("HUF", "Hungarian Forint"), ("RUB", "Russian Ruble"),
	("UAH", "Ukrainian Hryvnia"), ("ZAR", "South African Rand"), ("NGN", "Nigerian Naira"),
	("KES", "Kenyan Shilling"), ("MAD", "Moroccan Dirham"), ("DZD", "Algerian Dinar"),
]
CURRENCY_LABELS = ["%s - %s" % c for c in CURRENCIES]


def currency_code(label):
	return label.split(" - ")[0].strip().upper()


# (IANA name, standard UTC offset in minutes). The offset is only a fallback for PCs without time zone data.
TIMEZONES = [
	("UTC", 0), ("Europe/London", 0), ("Europe/Dublin", 0), ("Europe/Lisbon", 0), ("Atlantic/Reykjavik", 0),
	("Europe/Paris", 60), ("Europe/Berlin", 60), ("Europe/Madrid", 60), ("Europe/Rome", 60),
	("Europe/Amsterdam", 60), ("Europe/Stockholm", 60), ("Europe/Zurich", 60), ("Africa/Lagos", 60),
	("Africa/Casablanca", 60), ("Africa/Algiers", 60), ("Europe/Athens", 120), ("Europe/Kyiv", 120),
	("Africa/Cairo", 120), ("Africa/Johannesburg", 120), ("Asia/Jerusalem", 120), ("Asia/Beirut", 120),
	("Asia/Amman", 120), ("Europe/Istanbul", 180), ("Europe/Moscow", 180), ("Africa/Nairobi", 180),
	("Africa/Addis_Ababa", 180), ("Asia/Riyadh", 180), ("Asia/Baghdad", 180), ("Asia/Kuwait", 180),
	("Asia/Qatar", 180), ("Asia/Tehran", 210), ("Asia/Dubai", 240), ("Asia/Muscat", 240), ("Asia/Baku", 240),
	("Asia/Kabul", 270), ("Asia/Karachi", 300), ("Asia/Tashkent", 300), ("Asia/Kolkata", 330),
	("Asia/Colombo", 330), ("Asia/Kathmandu", 345), ("Asia/Dhaka", 360), ("Asia/Yangon", 390),
	("Asia/Bangkok", 420), ("Asia/Jakarta", 420), ("Asia/Ho_Chi_Minh", 420), ("Asia/Singapore", 480),
	("Asia/Kuala_Lumpur", 480), ("Asia/Hong_Kong", 480), ("Asia/Shanghai", 480), ("Asia/Manila", 480),
	("Asia/Taipei", 480), ("Australia/Perth", 480), ("Asia/Tokyo", 540), ("Asia/Seoul", 540),
	("Australia/Adelaide", 570), ("Australia/Sydney", 600), ("Australia/Brisbane", 600),
	("Pacific/Auckland", 720), ("Pacific/Honolulu", -600), ("America/Anchorage", -540),
	("America/Los_Angeles", -480), ("America/Vancouver", -480), ("America/Denver", -420),
	("America/Chicago", -360), ("America/Mexico_City", -360), ("America/New_York", -300),
	("America/Toronto", -300), ("America/Bogota", -300), ("America/Lima", -300), ("America/Caracas", -240),
	("America/Halifax", -240), ("America/Sao_Paulo", -180), ("America/Argentina/Buenos_Aires", -180),
]

COUNTRIES = [
	("Afghanistan", "AF"), ("Algeria", "DZ"), ("Argentina", "AR"), ("Australia", "AU"), ("Austria", "AT"),
	("Bahrain", "BH"), ("Bangladesh", "BD"), ("Belgium", "BE"), ("Brazil", "BR"), ("Canada", "CA"),
	("Chile", "CL"), ("China", "CN"), ("Colombia", "CO"), ("Czechia", "CZ"), ("Denmark", "DK"),
	("Egypt", "EG"), ("Ethiopia", "ET"), ("Finland", "FI"), ("France", "FR"), ("Germany", "DE"),
	("Ghana", "GH"), ("Greece", "GR"), ("Hong Kong", "HK"), ("Hungary", "HU"), ("India", "IN"),
	("Indonesia", "ID"), ("Iran", "IR"), ("Iraq", "IQ"), ("Ireland", "IE"), ("Italy", "IT"),
	("Japan", "JP"), ("Jordan", "JO"), ("Kenya", "KE"), ("Kuwait", "KW"), ("Lebanon", "LB"),
	("Malaysia", "MY"), ("Mexico", "MX"), ("Morocco", "MA"), ("Nepal", "NP"), ("Netherlands", "NL"),
	("New Zealand", "NZ"), ("Nigeria", "NG"), ("Norway", "NO"), ("Oman", "OM"), ("Pakistan", "PK"),
	("Peru", "PE"), ("Philippines", "PH"), ("Poland", "PL"), ("Portugal", "PT"), ("Qatar", "QA"),
	("Romania", "RO"), ("Russia", "RU"), ("Saudi Arabia", "SA"), ("Singapore", "SG"), ("South Africa", "ZA"),
	("South Korea", "KR"), ("Spain", "ES"), ("Sri Lanka", "LK"), ("Sweden", "SE"), ("Switzerland", "CH"),
	("Thailand", "TH"), ("Turkey", "TR"), ("Ukraine", "UA"), ("United Arab Emirates", "AE"),
	("United Kingdom", "GB"), ("United States", "US"), ("Vietnam", "VN"),
]
COUNTRY_NAMES = [c[0] for c in COUNTRIES]
COUNTRY_CODE = dict(COUNTRIES)

LANGUAGES = [
	"English", "Arabic", "Urdu", "Hindi", "Tamil", "Telugu", "Malayalam", "Kannada", "Bengali", "Punjabi",
	"Gujarati", "Marathi", "Sinhala", "Nepali", "Persian", "Turkish", "French", "Spanish", "Portuguese",
	"German", "Italian", "Dutch", "Russian", "Ukrainian", "Polish", "Swedish", "Greek", "Hebrew",
	"Chinese (Simplified)", "Chinese (Traditional)", "Japanese", "Korean", "Indonesian", "Malay", "Thai",
	"Vietnamese", "Filipino", "Swahili", "Hausa", "Amharic", "Pashto",
]

CITIES = [
	"New York", "Los Angeles", "Chicago", "Houston", "Toronto", "Vancouver", "Mexico City", "Sao Paulo",
	"Buenos Aires", "London", "Manchester", "Dublin", "Paris", "Berlin", "Madrid", "Rome", "Amsterdam",
	"Istanbul", "Moscow", "Cairo", "Lagos", "Nairobi", "Johannesburg", "Casablanca", "Riyadh", "Jeddah",
	"Mecca", "Medina", "Dubai", "Abu Dhabi", "Doha", "Kuwait City", "Muscat", "Tehran", "Baghdad", "Karachi",
	"Lahore", "Islamabad", "Delhi", "Mumbai", "Chennai", "Bengaluru", "Hyderabad", "Kolkata", "Colombo",
	"Kathmandu", "Dhaka", "Bangkok", "Singapore", "Kuala Lumpur", "Jakarta", "Manila", "Hong Kong",
	"Shanghai", "Beijing", "Tokyo", "Seoul", "Sydney", "Melbourne", "Auckland",
]

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
	"October", "November", "December"]

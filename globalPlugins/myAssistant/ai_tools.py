# -*- coding: UTF-8 -*-
"""70 AI tools. Each tool is a small description: what to ask the user (with combo boxes for every choice)
and the instruction sent to the AI provider chosen in NVDA settings."""
import api
import addonHandler
from . import providers
from .common import ask_form, run_async, speak
from .data import LANGUAGES

addonHandler.initTranslation()

SYSTEM = ("You are a helpful assistant inside a screen reader add-on. Reply in plain text only. "
	"Never use markdown symbols such as asterisks, hash signs, backticks or tables with dashes. "
	"Organize the answer with short paragraphs or numbered lines so it is easy to read aloud. "
	"When you write code, give only the code lines, without code fences.")

TONES = ["Formal", "Friendly", "Professional", "Casual", "Polite", "Persuasive", "Empathetic", "Confident"]
LEVELS = ["A child (age 8)", "A teenager", "A complete beginner", "An intermediate learner", "An expert"]
LENGTHS = ["Very short", "Short", "Medium", "Long"]
DIETS = ["No special diet", "Vegetarian", "Vegan", "Halal", "Gluten free", "Low carb", "High protein"]
CODE_LANGS = ["Python", "JavaScript", "C#", "Java", "C++", "C", "PHP", "SQL", "HTML and CSS", "PowerShell",
	"Bash", "Go", "Rust", "Kotlin", "Swift", "TypeScript"]
COUNTS = ["3", "5", "10", "15", "20"]


def C(key, label, choices, default=None):
	return {"key": key, "label": label, "type": "combo", "choices": choices, "default": default}


def O(key, label):
	"""An optional text box."""
	return {"key": key, "label": label, "type": "text"}


def _clip_quiet():
	try:
		return (api.getClipData() or "")[:12000]
	except Exception:
		return ""


def T(cat, name, prompt, input=None, fields=(), clip=False, note=None):
	return {"cat": cat, "name": name, "prompt": prompt, "input": input, "fields": list(fields),
		"clip": clip, "note": note}


WRITE = "AI: writing and email"
LEARN = "AI: learning and study"
CODE = "AI: code and computer help"
ANALYZE = "AI: analysis and text tools"
LIFE = "AI: daily life"

TXT = _("Your &text (filled from the clipboard, you can edit it):")
SPECS = [
	# ------------------------------------------------------------ writing and email
	T(WRITE, "Summarize text", "Summarize the text below. Style: {style}.\n\n{text}", TXT,
		[C("style", _("Summary &style:"), ["One sentence", "Short paragraph", "Numbered key points", "Detailed summary"])], True),
	T(WRITE, "Translate text", "Translate the text below into {lang}. Reply with the translation only.\n\n{text}", TXT,
		[C("lang", _("Translate &into:"), LANGUAGES, "English")], True),
	T(WRITE, "Improve writing", "Improve the text below. Goal: {goal}. Keep the meaning and the language. "
		"Reply with the improved text only.\n\n{text}", TXT,
		[C("goal", _("&Goal:"), ["Fix grammar and spelling", "Make it clearer", "Make it shorter",
			"Make it more detailed", "Make it sound more natural", "Make it more professional"])], True),
	T(WRITE, "Change the tone of text", "Rewrite the text below in a {tone} tone. Keep the meaning and the language. "
		"Reply with the rewritten text only.\n\n{text}", TXT, [C("tone", _("&Tone:"), TONES)], True),
	T(WRITE, "Proofread and list corrections", "Proofread the text below. First give the corrected text, then a numbered "
		"list of every change and why it was made.\n\n{text}", TXT, [], True),
	T(WRITE, "Paraphrase text", "Paraphrase the text below in {n} different ways. Number each version.\n\n{text}", TXT,
		[C("n", _("Number of &versions:"), ["1", "2", "3", "5"], "3")], True),
	T(WRITE, "Expand text", "Expand the text below to make it {size}. Keep the same ideas and language.\n\n{text}", TXT,
		[C("size", _("&Make it:"), ["about twice as long", "about three times as long", "a full page long"])], True),
	T(WRITE, "Shorten text", "Shorten the text below to about {keep} of its length. Keep the key meaning and the "
		"language.\n\n{text}", TXT, [C("keep", _("&Keep about:"), ["75 percent", "50 percent", "25 percent", "10 percent"], "50 percent")], True),
	T(WRITE, "Write an email", "Write an email. Tone: {tone}. Length: {length}. Include a subject line. "
		"Details:\n\n{text}", _("What should the &email say (purpose and details)?"),
		[C("tone", _("&Tone:"), TONES, "Professional"), C("length", _("&Length:"), LENGTHS, "Short")]),
	T(WRITE, "Reply to a message", "Write a {tone} reply to the message below. Points to include: {extra}\n\nMessage:\n{text}",
		_("&Message you received (filled from the clipboard):"),
		[O("extra", _("Your &main points (optional):")), C("tone", _("&Tone:"), TONES, "Polite")], True),
	T(WRITE, "Write a formal letter or application", "Write a {kind}. Use a suitable formal format. Details:\n\n{text}",
		_("&Details (names, dates, reason):"),
		[C("kind", _("&Type of letter:"), ["Leave application", "Job application", "Resignation letter", "Complaint letter",
			"Recommendation letter", "Request letter", "Thank you letter", "Apology letter"])]),
	T(WRITE, "Write a cover letter", "Write a strong cover letter of {length} length for this job. Details:\n\n{text}",
		_("&Job title, company and your skills:"), [C("length", _("&Length:"), ["Short", "Medium", "Long"], "Medium")]),
	T(WRITE, "Write a social media post", "Write a {tone} post for {platform} about the topic below. Add a few "
		"suitable hashtags.\n\n{text}", _("&Topic or message:"),
		[C("platform", _("&Platform:"), ["LinkedIn", "Facebook", "X (Twitter)", "Instagram", "WhatsApp status", "YouTube description"]),
		C("tone", _("&Tone:"), TONES, "Friendly")]),
	T(WRITE, "Write a speech", "Write a {tone} speech for this occasion: {occasion}. It should take about {minutes} "
		"to say aloud. Topic and details:\n\n{text}", _("&Topic and details:"),
		[C("occasion", _("&Occasion:"), ["Birthday", "Wedding", "Graduation", "Farewell", "Business presentation",
			"School assembly", "Award ceremony", "Welcome speech"]),
		C("minutes", _("&Speaking time:"), ["1 minute", "2 minutes", "3 minutes", "5 minutes", "10 minutes"], "3 minutes"),
		C("tone", _("&Tone:"), TONES, "Friendly")]),
	T(WRITE, "Write a product description", "Write a {tone} product description that would sell the product. Details:\n\n{text}",
		_("&Product details:"), [C("tone", _("&Tone:"), TONES, "Persuasive")]),
	T(WRITE, "Write a story", "Write an original {genre} story, {length} length, based on this idea:\n\n{text}",
		_("Your story &idea:"), [C("genre", _("&Genre:"), ["Adventure", "Mystery", "Comedy", "Fantasy", "Science fiction",
			"Moral story for children", "Drama", "Historical"]), C("length", _("&Length:"), LENGTHS, "Medium")]),
	T(WRITE, "Write a poem", "Write an original {style} poem about the theme below.\n\n{text}", _("&Theme:"),
		[C("style", _("&Style:"), ["Rhyming poem", "Free verse", "Haiku", "Limerick", "Ballad", "Ghazal style"])]),
	T(WRITE, "Generate titles and headlines", "Suggest {n} catchy titles or headlines for this. Number them.\n\n{text}",
		_("&Topic or text:"), [C("n", _("&How many:"), COUNTS, "10")], True),
	# ------------------------------------------------------------ learning and study
	T(LEARN, "Explain a topic", "Explain the topic below to {level}. Use simple examples.\n\n{text}", _("&Topic:"),
		[C("level", _("Explain to &whom:"), LEVELS, "A complete beginner")]),
	T(LEARN, "Explain text in simple words", "Rewrite and explain the text below so that {level} can understand it.\n\n{text}",
		TXT, [C("level", _("Explain to &whom:"), LEVELS, "A complete beginner")], True),
	T(LEARN, "Solve a math problem step by step", "Solve this math problem. Show every step in words so it can be read "
		"aloud, and state the final answer clearly.\n\n{text}", _("&Problem:")),
	T(LEARN, "Homework helper", "Answer this {subject} question. Explain the reasoning so a student can learn from it."
		"\n\n{text}", _("&Question:"),
		[C("subject", _("&Subject:"), ["Mathematics", "Physics", "Chemistry", "Biology", "History", "Geography",
			"English", "Computer science", "Economics", "Islamic studies", "General knowledge"])]),
	T(LEARN, "Create a quiz", "Create a quiz with {n} {kind} on the material below. Give the answer key at the end."
		"\n\n{text}", _("&Topic or study text:"),
		[C("n", _("&Number of questions:"), COUNTS, "10"),
		C("kind", _("Question &type:"), ["multiple choice questions with four options", "true or false questions",
			"short answer questions", "fill in the blank questions"])], True),
	T(LEARN, "Create flashcards", "Create {n} flashcards from the material below. Write each as Question: ... "
		"Answer: ... and number them.\n\n{text}", _("&Topic or study text:"), [C("n", _("&Number of cards:"), COUNTS, "10")], True),
	T(LEARN, "Study plan", "Create a study plan for: {text}\nTime available: {duration}, {hours} of study per day. "
		"Organize it by day or week with clear goals.", _("&Subject or exam:"),
		[C("duration", _("&Duration:"), ["1 week", "2 weeks", "1 month", "2 months", "3 months", "6 months"], "1 month"),
		C("hours", _("&Study hours per day:"), ["1 hour", "2 hours", "3 hours", "4 hours", "6 hours"], "2 hours")]),
	T(LEARN, "Essay outline", "Create a detailed outline for a {kind} on this topic:\n\n{text}", _("&Topic:"),
		[C("kind", _("&Type of essay:"), ["Argumentative essay", "Descriptive essay", "Narrative essay",
			"Research paper", "Report", "Speech", "Book review"])]),
	T(LEARN, "Write an essay", "Write a {words} essay for {level} on this topic:\n\n{text}", _("&Topic:"),
		[C("words", _("&Length:"), ["300 words", "500 words", "800 words", "1200 words"], "500 words"),
		C("level", _("Written &for:"), ["School student", "College student", "University student", "General reader"])]),
	T(LEARN, "Vocabulary helper", "Explain the word or phrase below in {lang}: meaning, part of speech, three example "
		"sentences, synonyms and antonyms.\n\n{text}", _("&Word or phrase:"),
		[C("lang", _("Explain &in:"), LANGUAGES, "English")]),
	T(LEARN, "Grammar helper", "Check the sentence or paragraph below. Give the corrected version, then explain each "
		"grammar mistake in simple words.\n\n{text}", TXT, [], True),
	T(LEARN, "Language practice sentences", "Create {n} practice sentences in {lang} at {level} level about: {text}. "
		"After each sentence give its English meaning.", _("&Topic:"),
		[C("lang", _("Language to &practice:"), LANGUAGES, "English"), C("n", _("&Number of sentences:"), COUNTS, "10"),
		C("level", _("&Level:"), ["Beginner", "Intermediate", "Advanced"])]),
	T(LEARN, "Interview practice", "Give {n} likely {level} interview questions for this job, each followed by a "
		"strong sample answer.\n\n{text}", _("&Job role:"),
		[C("n", _("&Number of questions:"), COUNTS, "5"), C("level", _("&Level:"), ["entry level", "mid level", "senior level"])]),
	T(LEARN, "Memory aid and mnemonics", "Create memorable mnemonics or memory tricks to learn the following:\n\n{text}",
		_("&What do you want to memorize?"), [], True),
	# ------------------------------------------------------------ code and computer help
	T(CODE, "Write code", "Write {lang} code for the task below. Add short comments.\n\n{text}", _("&What should the code do?"),
		[C("lang", _("Programming &language:"), CODE_LANGS)]),
	T(CODE, "Explain code", "Explain what the code below does, step by step, in simple words.\n\n{text}",
		_("&Code (filled from the clipboard):"), [], True),
	T(CODE, "Find and fix bugs", "Find the bugs in the code below. List each problem, then give the corrected "
		"code.\n\n{text}", _("&Code (filled from the clipboard):"), [], True),
	T(CODE, "Convert code to another language", "Convert the code below to {lang}. Give only the converted code.\n\n{text}",
		_("&Code (filled from the clipboard):"), [C("lang", _("Convert &to:"), CODE_LANGS)], True),
	T(CODE, "Write test cases for code", "Write {lang} unit tests for the code below.\n\n{text}",
		_("&Code (filled from the clipboard):"), [C("lang", _("Test &language:"), CODE_LANGS)], True),
	T(CODE, "Explain an error message", "Explain this error message in simple words. Give the most likely causes and "
		"numbered steps to fix it.\n\n{text}", _("&Error message (filled from the clipboard):"), [], True),
	T(CODE, "Write a regular expression", "Write a {flavor} regular expression for this. Give the pattern, a short "
		"explanation and two examples.\n\n{text}", _("&What should it match?"),
		[C("flavor", _("Regex &flavor:"), ["Python", "JavaScript", ".NET", "PCRE", "Java"])]),
	T(CODE, "Spreadsheet formula helper", "Write the {app} formula for this and explain how it works.\n\n{text}",
		_("&What do you want to calculate?"), [C("app", _("&Application:"), ["Microsoft Excel", "Google Sheets", "LibreOffice Calc"])]),
	T(CODE, "Command line helper", "Give the {shell} command for this task and explain each part.\n\n{text}",
		_("&What do you want to do?"), [C("shell", _("&Shell:"), ["Windows PowerShell", "Windows Command Prompt",
			"Linux Bash", "macOS Terminal"])]),
	T(CODE, "Windows and NVDA how-to helper", "Give clear numbered keyboard-only steps for a screen reader user who uses "
		"NVDA on Windows. Question:\n\n{text}", _("&What do you want to know how to do?")),
	T(CODE, "Improve my AI prompt", "Rewrite the prompt below so an AI assistant gives a better answer. Make it "
		"specific and clear. Give only the improved prompt.\n\n{text}", _("&Your prompt:"), [], True),
	# ------------------------------------------------------------ analysis and text tools
	T(ANALYZE, "Extract key points", "List the {n} most important points of the text below as numbered lines.\n\n{text}", TXT,
		[C("n", _("&Number of points:"), ["3", "5", "7", "10"], "5")], True),
	T(ANALYZE, "Extract action items and deadlines", "From the text below list every task, who is responsible and any "
		"deadline. If something is not stated, write not stated.\n\n{text}", TXT, [], True),
	T(ANALYZE, "Write meeting minutes", "Turn the notes below into clear meeting minutes with: summary, decisions, "
		"action items and next steps.\n\n{text}", _("&Meeting notes (filled from the clipboard):"), [], True),
	T(ANALYZE, "Sentiment and tone analysis", "Analyze the sentiment and tone of the text below. Say whether it is positive, "
		"negative or neutral, list the emotions you find and give a short explanation.\n\n{text}", TXT, [], True),
	T(ANALYZE, "Pros and cons", "List the pros and the cons of this, then give a balanced conclusion.\n\n{text}",
		_("&Topic or decision:")),
	T(ANALYZE, "Compare two things", "Compare the two things below. Cover the main differences, similarities and "
		"which suits which kind of person.\n\n{text}", _("&Two things to compare (for example A and B):")),
	T(ANALYZE, "Decision helper", "Help me decide. Ask no questions. List the options, criteria to weigh, risks, and "
		"give a clear suggestion with your reasoning.\n\n{text}", _("Describe your &decision:")),
	T(ANALYZE, "Brainstorm ideas", "Brainstorm {n} creative ideas for this. Number them and add one line about each."
		"\n\n{text}", _("&Topic or problem:"), [C("n", _("&How many ideas:"), COUNTS, "10")]),
	T(ANALYZE, "Fact-check claims", "List each factual claim in the text below and say whether it is generally accurate, "
		"inaccurate or uncertain, with a short reason. State clearly if you are unsure and that the user should "
		"verify important facts with reliable sources.\n\n{text}", TXT, [], True),
	T(ANALYZE, "Detect the language", "Identify the language of the text below, and give its English translation."
		"\n\n{text}", TXT, [], True),
	T(ANALYZE, "Keywords and hashtags", "Extract {n} keywords and {n} suitable hashtags from the text below.\n\n{text}", TXT,
		[C("n", _("&How many of each:"), ["3", "5", "10", "15"], "5")], True),
	T(ANALYZE, "Extract names, dates, places and numbers", "From the text below list all people, organizations, places, dates, "
		"times, amounts and phone numbers or emails, grouped under headings.\n\n{text}", TXT, [], True),
	T(ANALYZE, "Convert text to another format", "Convert the text below into this format: {fmt}. Give only the "
		"result.\n\n{text}", TXT,
		[C("fmt", _("&Format:"), ["Numbered list", "Bulleted list with hyphens", "CSV", "JSON",
			"Rows separated by a vertical bar", "Question and answer pairs"])], True),
	T(ANALYZE, "Ask a question about the text", "Answer the question using only the text below. If the answer is not in "
		"the text, say so.\n\nText:\n{text}\n\nQuestion: {question}", TXT,
		[{"key": "question", "label": _("Your &question about the text:"), "type": "text", "required": True}], True),
	T(ANALYZE, "Clean text for reading aloud", "Clean the text below for a screen reader: remove decorative symbols, "
		"emoji, repeated punctuation, web addresses noise and formatting marks, and keep all the real content. "
		"Give only the cleaned text.\n\n{text}", TXT, [], True),
	T(ANALYZE, "Ask AI a question", "{style}\n\nQuestion: {text}", _("Your &question:"),
		[C("style", _("Answer &style:"), ["Give a short answer.", "Give a detailed answer.", "Explain step by step.",
			"Explain like I am a complete beginner."])]),
	# ------------------------------------------------------------ daily life
	T(LIFE, "Recipe from ingredients", "Suggest a {diet} recipe for {n} people using mostly these ingredients. Give "
		"the ingredient amounts and numbered steps.\n\n{text}", _("&Ingredients you have:"),
		[C("diet", _("&Diet:"), DIETS), C("n", _("&Servings:"), ["1", "2", "4", "6", "8"], "4")]),
	T(LIFE, "Meal plan", "Create a {days} meal plan with breakfast, lunch, dinner and a snack each day. Diet: {diet}. "
		"Notes: {text}", _("&Preferences and things to avoid (or write none):"),
		[C("days", _("&Plan for:"), ["3 days", "5 days", "7 days", "14 days"], "7 days"), C("diet", _("&Diet:"), DIETS)],
		note=_("General information only. Ask a doctor or dietitian for personal medical advice.")),
	T(LIFE, "Travel itinerary", "Plan a {days} trip to the destination below. Budget level: {budget}. Give a day by day "
		"plan with places, food and travel tips.\n\n{text}", _("&Destination:"),
		[C("days", _("&Days:"), ["1 day", "2 days", "3 days", "5 days", "7 days", "10 days"], "3 days"),
		C("budget", _("&Budget:"), ["Low", "Medium", "High"], "Medium")]),
	T(LIFE, "Workout plan", "Create a {days} per week {goal} workout plan for {level}. Give each day's exercises with "
		"sets and repetitions, and safety tips. Notes: {text}", _("&Equipment or limits (or write none):"),
		[C("goal", _("&Goal:"), ["fat loss", "muscle building", "general fitness", "flexibility", "stamina"]),
		C("level", _("&Level:"), ["a beginner", "an intermediate", "an advanced person"]),
		C("days", _("&Days:"), ["2 days", "3 days", "4 days", "5 days", "6 days"], "3 days")],
		note=_("General information only. Check with a doctor before starting a new exercise plan.")),
	T(LIFE, "Gift ideas", "Suggest 10 thoughtful gift ideas for the occasion {occasion}, with a budget of {budget}. "
		"About the person:\n\n{text}", _("&Who is it for, and what do they like?"),
		[C("occasion", _("&Occasion:"), ["Birthday", "Wedding", "Anniversary", "Eid", "Christmas", "Graduation",
			"Thank you", "Housewarming"]),
		C("budget", _("&Budget:"), ["Low", "Medium", "High", "Any"], "Medium")]),
	T(LIFE, "Name ideas", "Suggest 15 {kind} name ideas with a short meaning or reason for each.\n\n{text}",
		_("&Details or preferences:"), [C("kind", _("Name &for:"), ["Baby", "Business", "Pet", "Product", "App or website",
			"Channel or podcast", "Team"])]),
	T(LIFE, "Explain a medical or legal document", "Explain the {kind} text below in simple words. Highlight important "
		"points, deadlines and terms to be careful about.\n\n{text}", TXT,
		[C("kind", _("&Type:"), ["medical report", "prescription", "legal contract", "official letter", "terms and conditions"])],
		True, _("This is a plain-language explanation, not professional advice. Please check with a doctor or lawyer.")),
	T(LIFE, "Budget planner", "Create a simple monthly budget plan from the details below. Show suggested amounts "
		"for needs, wants and savings, and tips to save money.\n\n{text}",
		_("&Monthly income and expenses:")),
	T(LIFE, "Daily schedule planner", "Create a realistic daily schedule for me. Available time: {hours}. Include "
		"short breaks. My tasks:\n\n{text}", _("&Tasks and priorities:"),
		[C("hours", _("&Hours available:"), ["2 hours", "4 hours", "6 hours", "8 hours", "10 hours", "12 hours"], "8 hours")]),
	T(LIFE, "Make a shopping list", "Turn the text below into a tidy shopping list grouped by store section.\n\n{text}",
		_("&Text or recipe:"), [], True),
	T(LIFE, "Trivia game questions", "Create {n} {level} trivia questions with answers on this topic:\n\n{text}",
		_("&Topic:"), [C("n", _("&Number of questions:"), COUNTS, "10"), C("level", _("&Difficulty:"), ["easy", "medium", "hard"])]),
	T(LIFE, "Joke or riddle", "Tell me {n} {kind} about the topic below (if no topic is given, choose any). Keep it "
		"clean and family friendly.\n\n{text}", _("&Topic (optional):"),
		[C("kind", _("&Kind:"), ["funny jokes", "riddles with answers", "puns", "tongue twisters"]),
		C("n", _("&How many:"), ["1", "3", "5"], "3")]),
]
OPTIONAL_INPUT = {"Joke or riddle"}


def _make(spec):
	title = spec["name"]

	def run():
		fields = []
		if spec["input"]:
			fields.append({"key": "text", "label": spec["input"], "type": "multiline",
				"default": _clip_quiet() if spec["clip"] else "", "required": title not in OPTIONAL_INPUT})
		fields += spec["fields"]
		r = ask_form(_("AI: %s") % _(title), fields)
		if not r:
			return
		r.setdefault("text", "")
		prompt = spec["prompt"].format(**r)
		note = spec["note"]

		def work():
			out = providers.ask([{"role": "user", "content": prompt}], system=SYSTEM)
			return out + ("\n\n" + note if note else "")
		run_async(work, _("AI: %s") % _(title))
	run.__name__ = "ai_" + "".join(ch if ch.isalnum() else "_" for ch in title.lower())
	return run


def _build():
	cats = {}
	order = []
	for s in SPECS:
		if s["cat"] not in cats:
			cats[s["cat"]] = []
			order.append(s["cat"])
		cats[s["cat"]].append((_("AI: %s") % _(s["name"]), _make(s)))
	return [(c, cats[c]) for c in order]


AI_CATEGORIES = _build()
AI_COUNT = sum(len(v) for _c, v in AI_CATEGORIES)

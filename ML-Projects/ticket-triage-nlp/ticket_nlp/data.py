"""Synthetic customer-support tickets.

Tickets are built from hand-written phrasing templates plus greetings, filler,
slot values, typos and *secondary issues* that mention a different category. The
label always follows the **primary** issue, so some tickets are genuinely
ambiguous, as in a real inbox. Each ticket records which template produced its
primary issue, which lets evaluation hold out whole phrasings.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CATEGORIES = ["billing", "technical_issue", "account_access", "shipping", "feature_request", "security"]
CATEGORY_WEIGHTS = [0.24, 0.22, 0.18, 0.14, 0.12, 0.10]

TEMPLATES: dict[str, list[str]] = {
    "billing": [
        "I was charged {amount} twice for my {plan} subscription this month",
        "Please refund the {amount} charge from {day}, I cancelled before the renewal",
        "My invoice for the {plan} plan shows the wrong total and I need a corrected receipt",
        "The discount code was not applied and I paid the full price of {amount}",
        "Why did my card get billed {amount} when I downgraded to the {plan} plan?",
        "I need to update the credit card on file because my payment keeps getting declined",
        "There is an unexpected fee of {amount} on my statement from {day}",
        "Can you send me a VAT invoice for the {plan} payment made on {day}?",
    ],
    "technical_issue": [
        "The {product} app crashes every time I open the dashboard on my {device}",
        "Error 500 appears when I try to export my report, it worked fine last week",
        "Sync between my {device} and the web version stopped working since {day}",
        "The page loads forever and then shows a blank screen in the browser",
        "Notifications are delayed by hours and sometimes never arrive on my {device}",
        "Uploading files fails at 90 percent with a timeout message",
        "After the latest update the {product} search returns no results at all",
        "The integration with our calendar keeps disconnecting and throws an authentication error",
    ],
    "account_access": [
        "I cannot log in to my account, the password reset email never arrives",
        "My account is locked after too many sign in attempts and I need it unlocked",
        "I changed my phone number and now the two factor code goes to the old one",
        "How do I change the email address linked to my login?",
        "I forgot which email I used to register and I cannot sign in",
        "Please merge my two accounts, I get access denied on the older one",
        "The invite link to join my team workspace says it has expired",
        "I am stuck in a login loop and it keeps sending me back to the sign in page",
    ],
    "shipping": [
        "My order {order} was supposed to arrive on {day} but tracking has not updated in a week",
        "The package arrived damaged, the box was crushed and the item is broken",
        "I received the wrong item, I ordered a {product} but got something else",
        "Can I change the delivery address for order {order} before it ships?",
        "Tracking says delivered but nothing is at my door",
        "The courier left my parcel with a neighbour I do not know",
        "How long will international delivery to my country take for order {order}?",
        "Part of my order {order} is missing, only one of the two boxes came",
    ],
    "feature_request": [
        "It would be great if you could add a dark mode to the {product} app",
        "Please support exporting reports to Excel format in addition to PDF",
        "We would love an option to schedule messages to send at a later time",
        "Is there any plan to add a keyboard shortcut for quick search?",
        "Could you add bulk editing so we can update many items at once?",
        "A calendar view for tasks would really help our team plan the week",
        "I suggest letting users customise the dashboard widgets and their order",
        "Please consider adding an integration with {product} so we can sync our data",
    ],
    "security": [
        "I think someone accessed my account, I see logins from a country I have never visited",
        "I received a suspicious email pretending to be from your company asking for my password",
        "Our team found an exposed API key in a public repository and we need to revoke it immediately",
        "I want to report a vulnerability that lets users see other customers data",
        "There are transactions I did not make and I believe my account has been compromised",
        "Please delete all my personal data under GDPR and confirm in writing",
        "How is my data encrypted and where is it stored? Our compliance team needs details",
        "A phishing site is using your logo and I want to report it",
    ],
}

# Topical sentences customers add around the core complaint. They are shared by every template of a
# category, as real vocabulary is, which is what lets a model generalise to unseen phrasings.
CONTEXT = {
    "billing": [
        "This is about my invoice and the payment on my card",
        "I would like a refund or a corrected charge on my billing statement",
        "It affects my subscription and the amount I was billed",
    ],
    "technical_issue": [
        "The app is not working properly and I keep seeing an error",
        "It looks like a bug since the last update, it was fine before",
        "The problem happens on both the app and the browser",
    ],
    "account_access": [
        "I cannot get into my account or sign in with my password",
        "It seems to be a login problem with my email or verification code",
        "I need access to my account restored",
    ],
    "shipping": [
        "This is about my delivery and where the parcel is",
        "The courier and the tracking information do not match what I ordered",
        "I am waiting for my package and need an update on the shipment",
    ],
    "feature_request": [
        "It would really improve the product for our team",
        "This is just a suggestion for a future release",
        "Many other users would benefit from this feature",
    ],
    "security": [
        "I am worried about the safety and privacy of my data",
        "This looks like a security risk and needs attention",
        "I am concerned someone unauthorised may have gained access",
    ],
}
CONTEXT_RATE = 0.6

GREETINGS = ["Hi team,", "Hello,", "Good morning,", "Hey there,", "Dear support,", ""]
FILLER = [
    "Thanks for your help.",
    "This is quite urgent for us.",
    "I have been a customer for {years} years.",
    "Let me know what you need from me.",
    "I already tried restarting everything.",
    "Please get back to me as soon as possible.",
    "I am using the latest version.",
    "",
]
SLOTS = {
    "amount": ["$9.99", "$24.00", "$49.00", "$120.50", "$7.50", "$199.00"],
    "plan": ["basic", "pro", "team", "business", "starter"],
    "day": ["Monday", "last Friday", "March 3rd", "yesterday", "the 14th", "last week"],
    "product": ["Atlas", "Beacon", "Compass", "Dashly", "Echo"],
    "device": ["iPhone", "Android phone", "laptop", "tablet", "desktop"],
    "order": ["#48213", "#90377", "#10452", "#66120", "#73894"],
    "years": ["2", "3", "5", "8"],
}


@dataclass(frozen=True)
class Ticket:
    ticket_id: int
    category: str
    template_id: str  # "category:index" of the primary issue; used as the group for evaluation
    text: str
    has_secondary_issue: bool
    secondary_template_id: str | None = None  # template of the distractor issue, if any


def _fill(template: str, rng: np.random.Generator) -> str:
    out = template
    for key, options in SLOTS.items():
        token = "{" + key + "}"
        while token in out:
            out = out.replace(token, str(rng.choice(options)), 1)
    return out


def corrupt_text(text: str, rate: float, rng: np.random.Generator) -> str:
    """Inject typos: each word is independently swapped, shortened or doubled with probability ``rate``."""
    if rate <= 0:
        return text
    words = text.split(" ")
    for i, word in enumerate(words):
        if len(word) < 4 or rng.random() >= rate:
            continue
        pos = int(rng.integers(1, len(word) - 1))
        kind = int(rng.integers(0, 3))
        if kind == 0:  # swap two neighbouring letters
            word = word[:pos] + word[pos + 1] + word[pos] + word[pos + 2 :]
        elif kind == 1:  # drop a letter
            word = word[:pos] + word[pos + 1 :]
        else:  # double a letter
            word = word[:pos] + word[pos] + word[pos:]
        words[i] = word
    return " ".join(words)


def generate_tickets(n: int = 6000, seed: int = 5, typo_rate: float = 0.03, secondary_rate: float = 0.30) -> list[Ticket]:
    if n < len(CATEGORIES) * 20:
        raise ValueError("n is too small to cover every category")
    if not 0 <= typo_rate <= 1 or not 0 <= secondary_rate <= 1:
        raise ValueError("typo_rate and secondary_rate must be between 0 and 1")

    rng = np.random.default_rng(seed)
    tickets = []
    for i in range(n):
        category = str(rng.choice(CATEGORIES, p=CATEGORY_WEIGHTS))
        index = int(rng.integers(0, len(TEMPLATES[category])))
        parts = [_fill(TEMPLATES[category][index], rng)]
        if rng.random() < CONTEXT_RATE:
            parts.append(str(rng.choice(CONTEXT[category])))

        has_secondary = bool(rng.random() < secondary_rate)
        secondary_id = None
        if has_secondary:
            other = str(rng.choice([c for c in CATEGORIES if c != category]))
            other_index = int(rng.integers(0, len(TEMPLATES[other])))
            secondary = _fill(TEMPLATES[other][other_index], rng)
            secondary_id = f"{other}:{other_index}"
            parts.append("Also, " + secondary[0].lower() + secondary[1:])

        parts.append(_fill(str(rng.choice(FILLER)), rng))
        body = ". ".join(p.rstrip(".") for p in parts if p) + "."
        greeting = str(rng.choice(GREETINGS))
        text = f"{greeting} {body}".strip()
        if rng.random() < 0.10:  # terse ticket: only the primary sentence, lower-cased, no punctuation
            text = parts[0].lower().replace(",", "").replace("?", "")
        tickets.append(
            Ticket(i, category, f"{category}:{index}", corrupt_text(text, typo_rate, rng), has_secondary, secondary_id)
        )
    return tickets

"""
Few-shot classification prompt.

The examples below are deliberately chosen to teach category *boundaries*,
not just category definitions — most of them sit right next to a category
the model could plausibly confuse them with (see the inline notes). This is
why few-shot beats zero-shot here: the taxonomy is semantically tight
(e.g. "money is stuck" could mean a freeze, a fraud hold, or a slow
transfer), and only worked examples pin down which label applies when.
"""
from schemas import Classification

TAXONOMY = """\
- Account Access & Freezes: the account itself is locked, frozen, or under review by the company (not a specific transaction dispute, and not the user's account being hacked by a third party).
- Transfers & Payments: sending/receiving/moving money is slow, stuck, failed, or (positively) fast and reliable. Use this only for the mechanics of the transfer itself, not a fee charged on it or a bank-linking failure.
- Fraud & Security: unauthorized transactions, account takeover by a third party, phishing/scam attempts, or requests for stronger security controls (2FA, etc).
- Disputes & Refunds: a specific transaction the user authorized but is unhappy with (item never arrived, wrong charge, merchant issue) and the resolution/refund process for it. If the transaction was never authorized by the user at all, that's Fraud & Security instead.
- Identity Verification / KYC: document upload, selfie checks, proof-of-address, or limit-increase verification steps.
- Funding & Linking: adding/connecting a bank account, debit card, or credit card as a funding source. Failures here are about the link itself, not a transfer using it.
- Fees & Pricing: any complaint or question about a fee amount, a fee appearing unexpectedly, or a fee change. If a review complains about both a fee AND something else (e.g. slow support), include both labels.
- Customer Support: hold times, chatbot loops, unhelpful or excellent human support experiences. Applies when the support interaction itself is what's being evaluated, not just mentioned in passing.
- App Performance & Reliability: crashes, freezes, lag, incorrect on-screen data due to bugs. This is about the software behaving incorrectly, not the design being confusing.
- Usability & UX: navigation, layout, discoverability, visual design complaints or praise — the app works correctly but is hard/easy to use.
- Feature Requests: an explicit ask for new functionality that doesn't exist today.
- Other / Uncategorised: doesn't fit any category above, or too vague to classify.
"""

FEEDBACK_TYPES = """\
- bug: a technical defect — the app is broken or behaving incorrectly.
- complaint: dissatisfaction with a policy, process, or experience that is "working as designed" (e.g. a fee, a slow but functioning process, an unhelpful policy).
- feature_request: an explicit ask for new functionality.
- question: the user is asking how something works, not reporting a problem.
- churn_risk: the user explicitly says or strongly implies they are considering leaving or switching to a competitor.
- praise: the user is satisfied and has no ask or complaint — use this whenever sentiment is positive and none of the other types apply.
"""

SENTIMENT = """\
- positive: the user is satisfied or praising the experience.
- neutral: factual, mixed, or no clear emotional tone (includes plain questions).
- negative: the user is frustrated, dissatisfied, or reporting a problem.
"""

FEW_SHOT_EXAMPLES = [
    (
        "My account has been frozen for 9 days and nobody can tell me why. "
        "I have rent money stuck in there.",
        Classification(
            category=["Account Access & Freezes"],
            feedback_type="complaint",
            sentiment="negative",
        ),
    ),
    (
        "Someone got into my account and sent themselves $850 from my linked card. "
        "I never approved that transaction.",
        # Note the contrast with the example above: money is also "stuck"/gone here,
        # but the cause is a third party, not a company-side freeze -> Fraud & Security,
        # not Account Access & Freezes.
        Classification(
            category=["Fraud & Security"],
            feedback_type="complaint",
            sentiment="negative",
        ),
    ),
    (
        "I disputed a payment to a seller who never shipped my item. It's been three "
        "weeks and the status still just says 'in progress'.",
        # The user authorized this payment themselves — the complaint is about the
        # merchant/resolution process, so Disputes & Refunds, not Fraud & Security.
        Classification(
            category=["Disputes & Refunds"],
            feedback_type="complaint",
            sentiment="negative",
        ),
    ),
    (
        "Instant transfer fee jumped from 1.5% to 1.75% with zero notice. Sneaky way "
        "to raise fees on people who need their money fast.",
        # The mechanics of the transfer aren't the problem here — the fee is.
        # Fees & Pricing only, not Transfers & Payments.
        Classification(
            category=["Fees & Pricing"],
            feedback_type="complaint",
            sentiment="negative",
        ),
    ),
    (
        "Linking my Chase debit card fails every single time with a generic error code. "
        "Works fine in every other app I use.",
        # A funding source connection problem, not a transfer problem -> Funding & Linking.
        Classification(
            category=["Funding & Linking"],
            feedback_type="bug",
            sentiment="negative",
        ),
    ),
    (
        "Waited on hold for 40 minutes only to get disconnected. Called back and had "
        "to explain the entire situation from scratch again.",
        Classification(
            category=["Customer Support"],
            feedback_type="complaint",
            sentiment="negative",
        ),
    ),
    (
        "App crashes every time I try to open my transaction history. Been happening "
        "since the last update.",
        # A defect, not a design complaint -> App Performance & Reliability + bug.
        Classification(
            category=["App Performance & Reliability"],
            feedback_type="bug",
            sentiment="negative",
        ),
    ),
    (
        "The navigation is so confusing. I still can't figure out where to find my "
        "routing and account number without searching online.",
        # The app works, it's just hard to use -> Usability & UX, complaint (not a bug).
        Classification(
            category=["Usability & UX"],
            feedback_type="complaint",
            sentiment="negative",
        ),
    ),
    (
        "Would love a way to schedule recurring payments to the same person every "
        "month instead of manually sending it each time.",
        Classification(
            category=["Feature Requests"],
            feedback_type="feature_request",
            sentiment="neutral",
        ),
    ),
    (
        "Considering switching to a competitor after this account freeze nonsense. "
        "Two weeks with my money locked up is unacceptable.",
        # Multi-label: the root cause is a freeze, but the user is also signaling churn risk.
        # category captures the topic; feedback_type captures the churn intent.
        Classification(
            category=["Account Access & Freezes"],
            feedback_type="churn_risk",
            sentiment="negative",
        ),
    ),
    (
        "Sent money to my roommate for rent and it landed in her account in under a "
        "minute. So much easier than writing a check.",
        Classification(
            category=["Transfers & Payments"],
            feedback_type="praise",
            sentiment="positive",
        ),
    ),
    (
        "I'd feel safer if there was two factor authentication required for every new "
        "device login, not just sometimes.",
        # A security ask phrased as a suggestion -> still Fraud & Security (the security
        # domain), feedback_type is feature_request since nothing is broken.
        Classification(
            category=["Fraud & Security"],
            feedback_type="feature_request",
            sentiment="neutral",
        ),
    ),
]


def _format_example(text: str, classification: Classification) -> str:
    output = classification.model_dump_json()
    return f'Feedback: "{text}"\nOutput: {output}'


def build_system_prompt() -> str:
    examples = "\n\n".join(_format_example(text, c) for text, c in FEW_SHOT_EXAMPLES)
    return f"""You are PulseAI's feedback classifier for a consumer fintech payments app \
(a Cash App / Venmo / PayPal / Wise style product). Classify each piece of user \
feedback into exactly the JSON schema you are given.

## Topic categories (category is multi-label — include every category that genuinely applies)
{TAXONOMY}

## Feedback types (pick exactly one)
{FEEDBACK_TYPES}

## Sentiment (pick exactly one — this is tone, independent of category or severity)
{SENTIMENT}

## Worked examples
These examples were chosen specifically to show the boundary between categories \
that are easy to confuse. Pay attention to *why* each label was chosen, not just what it is.

{examples}

## Rules
- Output ONLY the JSON object matching the schema. No prose, no explanation.
- category must contain at least one topic and every topic that genuinely applies — do not force a single label if the feedback clearly spans more than one topic.
- If nothing fits, use "Other / Uncategorised".
- Never invent a category, feedback_type, or sentiment value outside the ones defined above.
"""


def build_user_prompt(feedback_text: str) -> str:
    return f'Feedback: "{feedback_text}"\nOutput:'

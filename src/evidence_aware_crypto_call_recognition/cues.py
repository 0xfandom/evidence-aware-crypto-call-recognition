"""Wording patterns for the policy's operations.

Each pattern names one policy idea (own entry, exit, short cover, conditional, ...).
They are matched against the unquoted view of a sentence, so quoted speech never
counts as the author's own action.
"""
from __future__ import annotations

import re

_I = re.IGNORECASE

NEGATION = re.compile(r"\b(?:not|no|never|neither|nor|without|cannot|rather\s+than|instead\s+of)\b|n['’]t\b", _I)
CLAUSE_BREAK = re.compile(r"[,;:—–()]|\bbut\b|\band\s+then\b", _I)

_ENTRY_ACTION = (
    r"(?:buy(?:ing)?|start(?:ing)?|open(?:ing)?|add(?:ing)?|accumulat(?:e|ing)|enter(?:ing)?|re-?enter(?:ing)?"
    r"|initiat(?:e|ing)|establish(?:ing)?|tak(?:e|ing)(?!\s+(?:some\s+|a\s+|more\s+)?(?:profits?|gains|break|notes?|questions?|time|look))"
    r"|load(?:ing)?(?:\s+up)?|grab(?:bing)?|pick(?:ing)?\s+up|scal(?:e|ing)\s+in(?:to)?|get(?:ting)?\s+(?:in|into|back\s+in)"
    r"|go(?:ing)?\s+long|long(?:ing)?\s+(?=\$)|allocat(?:e|ing)|increas(?:e|ing)|enlarg(?:e|ing)|top(?:ping)?\s+up|rebuy(?:ing)?"
    r"|build(?:ing)?\s+(?:a|an|my|our|the)\s+(?:\w+\s+)?(?:position|stake|allocation|bag)"
    r"|direct(?:ing)?\s+(?:(?:a|new|fresh|more|some|my|our)\s+)*(?:allocation|capital|funds|money)"
    r"|put(?:ting)?\s+(?:(?:new|fresh|more|some|my|our)\s+)*(?:capital|money|funds)\s+(?:in|into)"
    r"|put(?:ting)?\s+(?:\S+\s+){0,2}to\s+work\s+in(?:to)?|deploy(?:ing)?\s+(?:\S+\s+){0,2}into"
    r"|rotat(?:e|ing)\s+(?:\S+\s+){0,3}?into"
    r"|bid(?:ding)?|stack(?:ing)?|ap(?:e|ing)\s+in(?:to)?|keep(?:ing)?\s+(?:stacking|buying|adding|accumulating|bidding))"
)
_SUBJECT = r"\b(?:I|we|our\s+(?:desk|team|fund|book|portfolio|treasury|group)|my\s+(?:desk|fund|book|portfolio))"
_AUX = r"(?:\s+am|\s+are|\s+is|['’]m|['’]re|\s+will|['’]ll|\s+plan\s+to|\s+intend\s+to|\s+am\s+going\s+to|['’]m\s+going\s+to|\s+are\s+going\s+to)?"
_ADVERBS = r"(?:\s+(?:also|now|still|just|finally|officially|actively|gradually|slowly|happily|personally|again|quietly|already|then))*"

EXPLICIT_ENTRY = re.compile(_SUBJECT + _AUX + _ADVERBS + r"\s+" + _ENTRY_ACTION + r"\b", _I)
NEGATED_ENTRY = re.compile(
    _SUBJECT + r"(?:" + _AUX + r"\s+(?:not|never)|\s+(?:do|did|will|would|am|are)\s*(?:not|n['’]t)|['’]m\s+not|\s+won['’]t|\s+don['’]t)"
    + _ADVERBS + r"\s+" + _ENTRY_ACTION + r"\b", _I)
LEADING_ENTRY = re.compile(
    r"^[\W_]*(?:\$[A-Z][A-Z0-9]{2,11}\s*[:—–-]\s*)?(?:(?:also|now|just|still|finally|today|here)[\s,]+)*"
    r"(?:adding|buying|starting|accumulating|loading(?:\s+up)?|grabbing|entering|opening|taking|picking\s+up|scaling\s+in(?:to)?"
    r"|initiating|allocating|getting\s+(?:in|into)|going\s+long|bidding|topping\s+up"
    r"|longing|stacking|aping(?:\s+in(?:to)?)?|rotating\s+into)\b", _I)
CONJOINED_ENTRY = re.compile(
    r"\b(?:and|then|while|plus)\s+(?:(?:am|are|also|now|still|just)\s+)*"
    r"(?:adding|buying|starting|accumulating|loading(?:\s+up)?|grabbing|entering|opening\s+a\s+(?:new\s+|fresh\s+)?position|"
    r"picking\s+up|scaling\s+into|initiating|allocating|rotating\s+into|topping\s+up)\b", _I)
IMPERATIVE_ENTRY = re.compile(
    r"^[\W_]*(?:buy|start|add|accumulate|grab|enter|load\s+up(?:\s+on)?|pick\s+up|get\s+in(?:to)?|bid|open\s+a\s+position"
    r"|long(?=\s+\$)|ape\s+in(?:to)?|stack|keep\s+(?:stacking|buying|accumulating|adding|bidding))\b", _I)
BUYER_STANCE = re.compile(
    r"\b(?:I|we)(?:['’]m|\s+am|['’]re|\s+are)\s+(?:now\s+|still\s+)?an?\s+buyers?\b"
    r"|\bwhere\s+(?:I|we)\s+want\s+(?:(?:new\s+|fresh\s+|more\s+)?exposure|to\s+(?:be|own|add))\b|\bcount\s+(?:me|us)\s+in\b"
    r"|\b(?:I|we)(?:['’]ve|\s+have)\s+(?:just\s+|now\s+)?(?:begun|started|been)\s+(?:building|buying|accumulating|adding|scaling)\b"
    r"|\b(?:I|we)(?:['’]ve|\s+have)\s+(?:just\s+)?(?:opened|started|initiated|established|taken)\s+(?:a|an|my|our)\s+(?:\w+\s+)?"
    r"(?:position|stake|allocation|long|entry)\b"
    r"|\b(?:I['’]m|I\s+am)\s+in(?:\s+too|\s+as\s+well)?(?=\s*(?:[.!]|$))", _I)

# Informal entry wording kept from the first version's rules (`rules.py`:
# IMPLICIT_BUY, the entry-price form of EXPLICIT_BUY, and ROTATION_INTO).
SLANG_ENTRY = re.compile(
    r"\bis\s+a\s+(?:gift|steal)\b|\b(?:best|generational|cheapest)\s+entry\b|\bsleep(?:ing|in['’]?)\s+on\b"
    r"|\bthis\s+is\s+the\s+spot\b|\bentry\s*(?:at|@|:)?\s*\$?\d", _I)
SLANG_NEGATIVE_FORM = re.compile(r"\bngmi\b|\bdo(?:n['’]t|\s+not)\s+fade\b", _I)
ROTATION_INTO = re.compile(r"\b(?:rotat(?:e|ing)|swap(?:ping)?|switch(?:ing)?|mov(?:e|ing)|going)\b[^.!?;]*?\binto(?=\s*\$)", _I)
# Joke and sarcasm markers kept from the same rules (SARCASM_POSSIBLE, SARCASM_CLEAR).
JOKE_MARKER = re.compile(r"🤡|🙃|😂|🤣|\blmf?ao\b|\blol\b|\bjk\b|what\s+could\s+(?:possibly\s+)?go\s+wrong|said\s+no\s+one", _I)

RECOMMENDED_ENTRY = re.compile(
    r"\b(?:my|our)\s+(?:own\s+)?(?:(?:current|new|latest|fresh|clear|actual)\s+)*"
    r"(?:recommendation|call|pick|plan|action|move|advice|view|trade|suggestion)\s+(?:today\s+|here\s+|now\s+)?is\s+(?:to\s+)?"
    + _ENTRY_ACTION + r"\b"
    r"|\b(?:I|we)\s+(?:would\s+|strongly\s+|now\s+)?(?:recommend|suggest|advise)\s+(?:(?:buying|accumulating|adding|starting|entering|opening|taking)\b|an?\s+(?:\w+\s+)?(?:entry|position|allocation))",
    _I)
IMPLICIT_ENTRY = re.compile(
    r"\b(?:new|fresh|starter|small|modest|initial|sensible|good|attractive|reasonable|solid|first|opening|measured|clean)\s+"
    r"(?:\w+\s+)?(?:position|allocation|entry|stake|buy)\b"
    r"|\b(?:earns|deserves|gets|has\s+earned|takes|wins)\s+an?\s+(?:new\s+|fresh\s+)?(?:place|spot|slot|seat)\s+in\s+(?:the|my|our)\b"
    r"|\b(?:current|good|attractive|clear|fresh|real)\s+entry\s+(?:opportunity|point|zone|window)\b"
    r"|\bentry\s+opportunity\b"
    r"|\bworth\s+(?:buying|accumulating|owning|adding|entering|starting|an\s+entry|a\s+(?:\w+\s+)?position|an\s+allocation)\b"
    r"|\b(?:is|looks|remains|still)\s+(?:a\s+|an?\s+\w+\s+)?buy\s+(?:here|now|today|at\s+this)\b"
    r"|\btime\s+to\s+(?:buy|accumulate|enter|start|add)\b"
    r"|\bmakes\s+sense\s+(?:to\s+me|here|now|today|for\s+me)\b",
    _I)
PRESENT_MARKER = re.compile(
    r"\b(?:here|now|today|tonight|right\s+now|this\s+(?:afternoon|morning|evening|week|session|zone|level|price|valuation|range)"
    r"|at\s+(?:this|these|the\s+current|current)\s+(?:level|price|valuation|zone|range|levels|prices)s?|in\s+this\s+(?:zone|range|area)"
    r"|current(?:ly)?|still\s+offers|fresh|new)\b", _I)

COVER_SHORT = re.compile(
    r"\bcover(?:ing|ed|s)?\b(?:\s+\S+){0,4}?\s+short\b|\bshort[- ]cover\w*|\bclos(?:e|ing|ed)\s+(?:\S+\s+){0,4}?short\b"
    r"|\bbuy(?:ing)?\s+back\s+(?:\S+\s+){0,3}?short\b|\bcover(?:ing|ed)?\s+(?:my|the|our)\s+(?:\S+\s+)?short", _I)
OPEN_SHORT = re.compile(
    r"\bshorting\b|\bgo(?:ing)?\s+short\b|\b(?:open|opening|opened|initiat\w+|enter\w*|start\w*|add(?:ing)?\s+to)\s+"
    r"(?:(?:a|an|my|the|new|fresh|small)\s+)*(?:\S+\s+)?short\b(?!\s+cover)|\bshort\s+(?:position|entry)\s+(?:on|in)\b"
    r"|\b(?:I|we)\s+(?:am|are|['’]m|['’]re)\s+(?:now\s+)?short\s+\$", _I)
EXIT = re.compile(
    r"\bsell(?:ing|s)?\b|\bsold\b|\bexit(?:ing|ed|s)?\b|\breduc(?:e|ing|ed)\b|\btrim(?:ming|med|s)?\b"
    r"|\btak(?:e|ing)\s+(?:some\s+|more\s+)?profits?\b|\btook\s+(?:some\s+)?profits?\b"
    r"|\bcut(?:ting)?\s+(?:my\s+|our\s+|the\s+)?(?:position|exposure|stake|loss(?:es)?)\b"
    r"|\bclos(?:e|ing|ed)\s+(?:out\s+)?(?:my|the|our)\s+(?:\w+\s+)?(?:long|position|stake)\b|\bunload(?:ing|ed)?\b|\bdump(?:ing|ed)?\b"
    r"|\bscal(?:e|ing)\s+out\b|\blighten(?:ing|ed)?\b|\brotat(?:e|ing|ed)\s+out\s+of\b|\bout\s+of\b|\bstepping\s+away\s+from\b", _I)
RECOMMENDED_EXIT = re.compile(r"\b(?:recommendation|call|plan|advice|action|move)\s+is\s+to\s+(?:sell|exit|trim|reduce|close|take\s+profits?|short)\b", _I)
HOLD = re.compile(
    r"\bexisting\b|\bholding\b|\bhodl\w*|\bstill\s+(?:hold\w*|own|in)\b|\b(?:I|we)\s+(?:still\s+)?(?:hold|own|keep)\b"
    r"|\bmy\s+(?:current\s+)?(?:position|bag|stake|holding)s?\b|\bremain\s+(?:long|invested|in)\b|\breporting\s+the\s+position\b"
    r"|\bposition\s+(?:report|update)\b|\b(?:I|we)\s+(?:am|are|['’]m|['’]re)\s+(?:still\s+)?long\b|\bsitting\s+on\b", _I)
PAST_ACQUISITION = re.compile(
    r"\b(?:bought|acquired|purchased|picked\s+up|got\s+into|got\s+in|entered|re-?entered|loaded\s+up|accumulated|aped\s+into|added|grabbed)\b"
    r"|\b(?:started|opened|initiated|established|took)\s+(?:a|an|my|our)\s+(?:\w+\s+){0,2}(?:position|stake|allocation|entry|long|bite)\b"
    r"|\bput\s+(?:\w+\s+){0,2}(?:capital|money|funds)\s+in(?:to)?\b|^[\W_]*back\s+in(?:to)?\s+(?=\$)", _I)
COUNTERFACTUAL = re.compile(r"\b(?:would|could|should|might)\s+have\b|\balmost\b|\bnearly\b|\bwish\s+(?:I|we)\s+had\b|\bif\s+(?:I|we)\s+had\b", _I)
HEDGE = re.compile(r"\bputs\s+(?:on|against)\b|\bput\s+options?\b|\bhedg\w*|\bprotective\b|\bprotection\b", _I)
HISTORIC_TIME = re.compile(
    r"\b(?:last\s+(?:week|month|year|summer|spring|winter|autumn|fall|cycle|night|time|quarter)|yesterday|ago|previously|formerly"
    r"|back\s+(?:then|in\s+(?:the\s+day|20\d\d|spring|summer|autumn|fall|winter|january|february|march|april|may|june|july"
    r"|august|september|october|november|december))|in\s+(?:spring|summer|autumn|fall|winter|20\d\d|january|february|march|april|may|june|july|august"
    r"|september|october|november|december)|history|historical|archive\w*|earlier\s+(?:this|in)|years?\s+back|at\s+the\s+time|old)\b", _I)
CURRENT_TIME = re.compile(r"\b(?:today|this\s+(?:morning|afternoon|evening|session)|just|moments\s+ago|right\s+now|now|tonight)\b", _I)
CONDITIONAL = re.compile(
    r"\b(?:if|once|unless|should|in\s+case|when)\b(?:[^.;]|\.(?=\d))*?\b(?:will|would|['’]ll|might|may|plan|consider\w*|look\w*\s+to|wait\w*|then"
    r"|dips?|drops?|falls?|breaks?|trades?|reach\w*|hits?|retests?|confirms?|clos\w+\s+(?:above|below))\b"
    r"|\bwait(?:ing)?\s+(?:for|until|on)\b|\buntil\s+then\b|\bonly\s+(?:if|when|after)\b|\b(?:I|we)\s+(?:am|are|['’]m|['’]re)\s+(?:still\s+)?waiting\b"
    r"|\bwould\s+(?:buy|consider|add|enter|start|look)\b|\bwill\s+consider\b|\bon\s+watch\b|\bwatchlist\b", _I)
FORECAST = re.compile(
    r"\b(?:might|could|may|likely|expect\w*|forecast\w*|predict\w*|scenario|estimate\w*|projection|target\w*|double|triple"
    r"|\d+x|moon\w*|upside|rally|outperform\w*|bullish|optimis\w*|potential)\b", _I)
DISCLAIMER = re.compile(
    r"\b(?:not|no|never|neither|nor|without)\b(?:\s+\S+){0,6}?\s+(?:recommend\w*|endors\w*|(?:trading\s+|investment\s+|portfolio\s+)?instruction"
    r"|renew\w*|propos\w*|portfolio\s+advice|trading\s+advice|entry\s+advice|new\s+(?:trade|position|entry|buy|long)|fresh\s+(?:entry|buy|position)"
    r"|buy\s+(?:call|signal)|signal|call\s+to\s+buy|(?:current\s+)?entry\s+recommendation|current\s+entry|buyer"
    r"|(?:more|new|additional|fresh)\s+exposure|chasing)\b"
    r"|\brecommends?\s+no\b|\bmakes?\s+no\s+(?:\w+\s+){0,2}(?:recommendation|call)\b", _I)
BOILERPLATE_DISCLAIMER = re.compile(r"\bnot\s+(?:financial|investment)\s+advice\b|\bnfa\b|\bdyor\b", _I)
OTHER_PARTY_POSSESSIVE = re.compile(
    r"\b(?:writer|author|announcement|promoter|poster|account|team|someone\s+else|somebody\s+else|another\s+\w+|other\s+\w+|caller|analyst)['’]s\b"
    r"|\b(?:their|his|her)\b", _I)
THIRD_PARTY = re.compile(
    r"\b(?:someone|somebody)\s+else\b|\banother\s+(?:\w+\s+)?(?:writer|author|trader|user|account|person|poster|analyst|caller|influencer)\b"
    r"|\bnot\s+mine\b|\b(?:he|she|they)\s+(?:is|are|was|were|said|says|claims?|thinks?|wrote|posted)\b|\baccording\s+to\b"
    r"|\b(?:their|his|her)\s+(?:call|entry|trade|pick|position|recommendation|note)\b|\bquoted\s+(?:position|call|entry|trade)\b"
    r"|\b(?:a|one|the)\s+(?:large|big|popular|other|another)?\s*(?:account|promoter|influencer|caller|channel)\s+(?:wrote|posted|said|says|claims)\b", _I)
CONTEXT_REFERENCE = re.compile(
    r"\b(?:quoted|parent|original|linked|referenced|retweeted|reposted|shared|above|previous|earlier|archived)\s+(?:\w+\s+)?"
    r"(?:post|announcement|note|tweet|message|bulletin|thread|update|call|reply)\b"
    r"|\bthe\s+(?:token|coin|asset|project|ticker|name)\s+(?:in|from|mentioned\s+in|named\s+in|behind|of)\b", _I)
SATIRE_FRAME = re.compile(
    r"\b(?:comedy|comedic|sketch|parod\w*|satir\w*|imitat\w*|impression\s+of|mocks|mocking|mockery|joke|joking|kidding|pretend\w*"
    r"|role-?play\w*|imaginary|spoof\w*|tongue[- ]in[- ]cheek|ironic(?:ally)?)\b|(?:^|\s)/s\b", _I)
SINCERITY = re.compile(r"\b(?:seriously|joke\s+aside|jokes\s+aside|separately|for\s+real|actually|in\s+earnest|honestly)\b", _I)
SPONSORSHIP = re.compile(
    r"\b(?:sponsored|sponsor|paid\s+(?:partnership|promotion|post|placement|collaboration)|advertisement|partnership\s+notice"
    r"|covered\s+this\s+post|compensated|affiliate|promo(?:tional)?)\b|#ad\b", _I)
NON_TOKEN_PURCHASE = re.compile(
    r"\b(?:subscription|software|app|membership|account\s+setup|checkout|course|licen[cs]e|chart\s+editor|ebook|ticket|merch"
    r"|referral|sign[- ]?up|signing\s+up|free\s+claim|claim\s+(?:your|a|the)\s+free|airdrop\s+claim|whitelist|giveaway|discount\s+code"
    r"|promo\s+code|hardware\s+wallet|device)\b", _I)
DEIXIS = re.compile(
    r"\b(?:the\s+opposite|exactly|same\s+(?:here|for\s+me|as\s+(?:you|above|that|the\s+parent))|agreed?|likewise|me\s+too|ditto"
    r"|seconded|this\s+one|that\s+one|the\s+one|same\s+trade|same\s+call|the\s+same|as\s+you\s+(?:did|said|suggested)?|with\s+you)\b|\+1", _I)
MARKET_EVALUATION = re.compile(
    r"\b(?:mistake|ignor\w*|chance|opportunit\w*|cheap|undervalued|overvalued|bargain|price|level|valuation|entry|buy|sell)\b", _I)
RHETORICAL_ENDORSEMENT = re.compile(
    r"\bwho\s+(?:in\s+their\s+right\s+mind\s+)?(?:wouldn['’]t|would\s+not|is\s+not|isn['’]t)\b|\bwhy\s+(?:wait|would\s+(?:anyone|you)\s+(?:wait|not))\b"
    r"|\bwhat\s+are\s+you\s+waiting\s+for\b|\b(?:isn['’]t|is\s+not)\s+(?:this|that|it)\s+(?:the|a)\s+(?:\w+\s+)?(?:entry|buy|opportunity)\b"
    r"|\bhow\s+is\s+this\s+not\s+a\s+buy\b", _I)
INSTRUCTION_TEXT = re.compile(
    r"\bignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier|your|other)\s+(?:instructions?|rules|prompts?|policy)\b"
    r"|\b(?:output|return|label|classify|mark)\s+(?:this\s+(?:post\s+)?)?(?:as\s+)?(?:a\s+)?(?:BUY|NO_NEW_BUY|UNCLEAR)\b"
    r"|\bsystem\s+prompt\b|\byou\s+are\s+(?:an?\s+)?(?:AI|assistant|model|classifier)\b", re.IGNORECASE)
POST_SCOPE = re.compile(r"\b(?:this|the\s+whole|today['’]s)\s+(?:post|note|message|thread|update|tweet)\b|\banything\s+(?:here|in\s+this)\b", _I)

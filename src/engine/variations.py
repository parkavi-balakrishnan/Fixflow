"""Deterministic Query Variation Generator for FixFlow.

Generates 8-10 distinct lexical/paraphrase variations for each canonical query,
covering multiple registers:
- Formal / Technical
- Casual / Conversational
- Keyword-based
- Frustrated / Urgent
- Typo-inclusive / Mobile shorthand
- Question-based / How-to
- Alternate symptom descriptions

Preserves the original troubleshooting intent without introducing unrelated symptoms.
"""
import re
from typing import Dict, List, Optional


def normalize_query_text(text: str) -> str:
    """Remove list numbering and normalize whitespace without changing meaning."""
    cleaned = re.sub(r'(?m)^\s*\d+\.\s*', '', text.strip())
    cleaned = cleaned.strip('"\' ')
    return " ".join(cleaned.split())


def _variation_key(text: str) -> str:
    """Return a punctuation-insensitive key for variation deduplication."""
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", text).lower().split())


# Curated, multi-register variations for the 20 official Samsung queries
_OFFICIAL_QUERY_VARIATIONS: Dict[int, List[str]] = {
    # 1. Tablet screen flashes and goes blank in Gmail
    1: [
        "Samsung tablet screen keeps flashing black whenever I try to open Gmail.",
        "Display blanks out completely after tapping on an email in the Gmail app on my A11 tablet.",
        "Galaxy tablet display flickers then turns off repeatedly when reading emails.",
        "tablet screen flikrs and goes black in gmail app after few seconds",
        "Samsung A11 tablet Gmail blank screen display flashing issue",
        "Why does my tablet screen shut off every single time I open an email? Very frustrating!",
        "How do I prevent my Galaxy tablet display from turning black when opening mail?",
        "Email application causes tablet display to blink and turn unresponsive.",
        "Samsung tablet display cuts to black intermittent flashing in mail app",
    ],
    # 2. Galaxy S22 screen turns completely blank or white
    2: [
        "Galaxy S22 screen turns solid white with no text when searching stock prices or using apps.",
        "My S22 display goes totally blank and displays nothing in Smart Tutor and other apps.",
        "phone screen stays completely white and text won't load on my Galaxy S22",
        "s22 screen white blank no text showing in apps stock search",
        "Samsung Galaxy S22 blank white screen display glitch across multiple applications",
        "My phone display is completely white and I can't read any text on my S22!",
        "How to resolve white screen freezing issue on Samsung Galaxy S22 phone?",
        "Display renders empty white background without text in search and Smart Tutor.",
        "S22 display goes blank white text missing app display failure",
    ],
    # 3. Galaxy Z Flip 7 screen went black, unable to use Smart Switch
    3: [
        "Galaxy Z Flip 7 display went completely dark and I cannot transfer data using Smart Switch.",
        "My Flip 7 screen is totally black, cannot interact with device or backup data.",
        "flip 7 screen went black cant see anything or use smart switch to transfer",
        "Samsung Z Flip 7 black screen data transfer failure smart switch",
        "My brand new Flip 7 screen is completely black and won't respond, need my data transferred now!",
        "How can I access my Galaxy Z Flip 7 files when the display stays pitch black?",
        "Z Flip 7 black display prevents touch interaction and Smart Switch data migration.",
        "Galaxy Z Flip 7 display unresponsive black screen Smart Switch blocked",
        "Screen black on Flip 7 device won't display anything to transfer data",
    ],
    # 4. Galaxy A15/A16 screen suddenly black after a month
    4: [
        "Samsung Galaxy A15 screen suddenly went pitch black and won't turn back on.",
        "My Galaxy A16 display died on its own after about one month of normal use.",
        "phone screen went black by itself after a month and won't turn on Samsung A15",
        "galaxy a15 a16 black screen suddenly wont turn on after month",
        "Samsung Galaxy A-series sudden display failure screen remains completely black",
        "Why did my Galaxy A16 screen suddenly go completely black after just a month?",
        "How to recover a Galaxy A15 screen that turned black and will not power up?",
        "Galaxy A15/A16 display completely unresponsive and black upon power button press.",
        "A16 display blacked out suddenly no screen output when powering on",
    ],
    # 5. Tablet screen stays blank during Smart Switch QR scan
    5: [
        "Galaxy tablet display remains completely blank when trying to scan Smart Switch QR code.",
        "Screen stays dark and won't display QR scanner for Smart Switch data transfer from S25.",
        "tablet screen stays blank during smart switch qr code scan from s25 phone",
        "Samsung tablet Smart Switch QR code scan blank screen transfer stuck",
        "I can't transfer data to my tablet because the screen stays blank during QR code scanning!",
        "How do I fix a blank screen preventing QR code scanning in Smart Switch on tablet?",
        "Smart Switch QR pairing displays black screen on Samsung tablet preventing transfer.",
        "Tablet display does not render camera or QR code during Smart Switch migration.",
        "Galaxy tablet blank screen Smart Switch QR transfer unable to proceed",
    ],
    # 6. Tablet screen dark, only three icons lit
    6: [
        "Tablet display stays dark with only three app icons visible and nothing else opening.",
        "My Samsung tablet screen is black except for three lit icons that won't launch.",
        "tablet screen dark only 3 icons lit up nothing loads or opens",
        "Samsung tablet dark screen three icons lit unresponsive apps won't load",
        "My tablet display is almost totally black with only 3 apps showing, device is unusable!",
        "How do I recover my tablet when only three app icons light up on a dark screen?",
        "Display illumination failure on tablet showing only three active icons on dark backdrop.",
        "Galaxy tablet partial screen illumination three icons visible apps not loading",
        "Only three icons appear on dark tablet screen and nothing responds to touch",
    ],
    # 7. Phone screen stays small, doesn't fill display
    7: [
        "My Samsung phone display stays shrunken in a small window and won't expand to full screen.",
        "Screen display shrunk down to a small area and won't fill the entire screen on new phone.",
        "phone main screen is tiny and wont expand to full size display",
        "Samsung phone small screen view won't expand full screen display mode",
        "Why is my main screen stuck tiny instead of filling the whole display?",
        "How to restore full screen display on Samsung phone when screen is small?",
        "Phone display remains minimized and does not scale to full panel dimensions.",
        "Galaxy phone main display stuck in compact window size won't stretch full",
        "Screen size reduced on Samsung device cannot get it back to full display",
    ],
    # 8. Galaxy Flip 7 inner screen stopped working, outer screen works
    8: [
        "Galaxy Flip 7 main folding screen stopped displaying or responding, but cover screen works fine.",
        "The inside screen of my Flip 7 is completely dead with no touch, while outer screen works.",
        "flip 7 inner screen not working no image or touch outer screen still works",
        "Galaxy Z Flip 7 inner display dead outer cover screen working touch issue",
        "My Flip 7 inside screen is totally unresponsive and dark, only the cover screen works!",
        "How to troubleshoot an inner screen failure on Galaxy Flip 7 when outer display works?",
        "Inner folding display unresponsive to touch with no video signal, outer screen functional.",
        "Flip 7 internal screen blacked out no touch response external cover screen normal",
        "Inner display failure on Samsung Flip 7 cover screen works normally",
    ],
    # 9. Galaxy Z Flip 6 screen flickers and goes blank when opened
    9: [
        "Samsung Galaxy Z Flip 6 display flickers and goes black every time I unfold the phone.",
        "Opening my Flip 6 makes the screen blink rapidly and turn completely blank.",
        "flip 6 screen flickers and goes blank when opened cant access settings",
        "Galaxy Z Flip 6 display flickers black screen upon unfolding hinge",
        "Every time I open my Z Flip 6 the screen flashes and goes dark, I can't even get into settings!",
        "How can I access settings on a Galaxy Flip 6 whose display turns blank on opening?",
        "Unfolding Galaxy Z Flip 6 triggers display flickering followed by complete screen blackout.",
        "Flip 6 screen blinking and turning black on fold opening settings inaccessible",
        "Display goes black upon opening Samsung Flip 6 flickering screen issue",
    ],
    # 10. Galaxy Flip 6 screen half black
    10: [
        "One half of my Galaxy Flip 6 screen is completely black while the other half works.",
        "My Flip 6 display is divided: half the screen is dark and dead, other side is normal.",
        "flip 6 screen is half black one side completely dark other side works",
        "Galaxy Z Flip 6 half display black split screen dark failure",
        "Half of my Z Flip 6 display went totally black and I can't access my device properly!",
        "What causes half the display on a Galaxy Flip 6 to turn completely black?",
        "Partial display failure on Flip 6 with one half blacked out and one half rendering.",
        "Galaxy Flip 6 split display one side pitch black other side functional",
        "Half of display dark on Samsung Flip 6 unable to use device normally",
    ],
    # 11. Floating circle shortcut on Galaxy S25
    11: [
        "There is a persistent floating circle on my Galaxy S25 screen and I want to remove it.",
        "How to turn off the hovering circular shortcut button for apps and navigation on Galaxy S25?",
        "floating circle icon on s25 screen shortcuts to recent apps want to get rid of it",
        "Galaxy S25 remove floating circle assistant menu shortcut icon",
        "How do I disable this annoying floating circle hovering all over my Galaxy S25 screen?",
        "Steps to disable the floating accessibility shortcut circle on Samsung Galaxy S25.",
        "Assistant menu floating circular overlay active on Galaxy S25 display disable procedure.",
        "Galaxy S25 floating widget circle overlay removal settings",
        "Can't remove floating circle on S25 screen that has shortcuts to home and back",
    ],
    # 12. Galaxy S22 screen stays blank, no activation message
    12: [
        "Galaxy S22 display remains blank and shows no activation message after carrier switch.",
        "My S22 screen is black with no activation prompt when powered on after deactivating old phone.",
        "s22 screen stays blank no activation message after carrier deactivated old device",
        "Samsung Galaxy S22 blank screen carrier activation message missing",
        "Switched to a new carrier but my Galaxy S22 screen is just blank with no setup message!",
        "How to get the activation message to appear on a blank Galaxy S22 screen?",
        "Device display stays dark without displaying network activation dialog post carrier transfer.",
        "S22 screen dark no activation notification displayed on initial power on",
        "Blank screen on Galaxy S22 after carrier activation old phone deactivated",
    ],
    # 13. Galaxy phone screen completely cracked
    13: [
        "My Samsung Galaxy phone screen is shattered and completely cracked, unable to use device.",
        "The display glass on my Galaxy is totally broken and cracked all over.",
        "phone screen completely cracked total crack cant use the phone",
        "Samsung Galaxy cracked screen shattered glass display replacement repair",
        "My phone screen is completely cracked and shattered, I can't touch or use it at all!",
        "What are my repair options for a completely cracked Galaxy phone screen?",
        "Galaxy smartphone display glass fully shattered and screen completely cracked.",
        "Galaxy phone broken glass display shattered total screen crack",
        "Device unusable due to totally cracked display screen on Galaxy phone",
    ],
    # 14. Galaxy S26 Ultra shows blue/black screen with tiny text
    14: [
        "Galaxy S26 Ultra displays a blue or black screen with tiny text and refuses to boot.",
        "My S26 Ultra won't start up, it just shows tiny error text on a blue screen.",
        "s26 ultra shows blue black screen with tiny text wont start holding power button doesnt work",
        "Samsung S26 Ultra blue screen tiny text startup failure",
        "My S26 Ultra is stuck on a blue screen with tiny text and holding the power button does nothing!",
        "How to recover a Galaxy S26 Ultra stuck on blue or black screen with small system text?",
        "Device boots to error console screen with small font on blue background fail to launch OS.",
        "Galaxy S26 Ultra unable to start with blue screen and small system text",
        "Screen blue with tiny text on S26 Ultra phone won't turn on past error",
    ],
    # 15. Screen flashes quickly in milliseconds when plugging charger
    15: [
        "Galaxy Ultra display flashes rapidly in milliseconds whenever I connect the charging cable.",
        "Plugging in my charger causes the screen to flicker extremely fast and becomes unusable.",
        "screen flashes extremely fast in milliseconds when plugging in charger samsung phone",
        "Samsung Ultra screen rapid millisecond flashing flicker on charger plug in",
        "Why does my screen rapidly flash every time I plug my phone into the charger?",
        "How to fix screen flashing quickly upon connecting USB-C charging cable on Samsung?",
        "Display exhibits rapid strobe-like flashing transient upon AC charger connection.",
        "Ultra screen flashes milliseconds when charging cable inserted unusable display",
        "Rapid screen flicker on charger connection on Samsung Galaxy Ultra device",
    ],
    # 16. Galaxy S24 screen completely blank with occasional scrolling
    16: [
        "Galaxy S24 display is completely dark with occasional scrolling and no visible content.",
        "My S24 screen went totally blank, cannot view data or use Smart Switch to transfer.",
        "s24 screen goes completely blank dark screen occasional scrolling cant transfer data",
        "Samsung Galaxy S24 blank dark screen no content Smart Switch data transfer blocked",
        "My Galaxy S24 screen is pitch dark with random scrolling and I can't transfer any of my data!",
        "How to backup data from a Galaxy S24 whose screen is dark with occasional scrolling?",
        "Galaxy S24 display stays black while the page occasionally scrolls.",
        "Galaxy S24 blank screen scrolling glitch unable to see content or transfer files",
        "Screen dark and blank on S24 phone Smart Switch data transfer impossible",
    ],
    # 17. Galaxy Z Flip 7 screen cracked at fold, touch not working
    17: [
        "Galaxy Z Flip 7 screen is cracked along the crease, touch is unresponsive and display is dim.",
        "Crease on my Z Flip 7 is cracked again, certain parts of touch dead and can hardly see display.",
        "flip 7 screen cracked at fold touch dead in parts hardly see display",
        "Galaxy Z Flip 7 folding crease crack touch unresponsive display degraded",
        "My Z Flip 7 screen cracked right where it folds, touch is broken and screen is barely visible!",
        "What to do when Galaxy Z Flip 7 screen cracks along the folding hinge and touch fails?",
        "Physical crease fracture on flexible display causing localized digitizer and visibility failure.",
        "Flip 7 folding line cracked touch not responding poor screen visibility",
        "Z Flip 7 hinge display crack partial touch failure display unreadable",
    ],
    # 18. Galaxy A17 screen distorted after receiving, needs diagnostics
    18: [
        "My new Galaxy A17 display looks distorted right out of the box and I need a diagnostic test.",
        "Screen on newly received Galaxy A17 has visual distortion, how do I run hardware diagnostics?",
        "galaxy a17 screen looks distorted brand new phone need diagnostic test",
        "Samsung Galaxy A17 distorted display new phone hardware diagnostic test",
        "Just got my Galaxy A17 and the screen is completely distorted, how do I test if it's defective?",
        "How to run display diagnostics on a Galaxy A17 showing distorted graphics?",
        "Visual artifacts and distortion present on Galaxy A17 display panel upon unboxing.",
        "Galaxy A17 screen distortion hardware test diagnostic check procedure",
        "Distorted display on new Galaxy A17 device looking for diagnostic tools",
    ],
    # 19. Galaxy S22 screen inputs delayed, touch laggy
    19: [
        "Galaxy S22 touchscreen response is delayed and laggy when typing or tapping.",
        "Noticeable touch lag and input delay when trying to interact with my Galaxy S22 screen.",
        "s22 screen inputs delayed touch responsiveness laggy noticeable delay",
        "Samsung Galaxy S22 touch screen lag delayed input responsiveness issue",
        "Why is there a huge delay between tapping and screen response on my Galaxy S22?",
        "How do I fix severe touchscreen input lag and delayed responsiveness on Galaxy S22?",
        "Digitizer latency and delayed input processing observed during user interaction on S22.",
        "Galaxy S22 touch delay laggy response to screen gestures and taps",
        "Touch screen responsiveness lag on Galaxy S22 delayed input behavior",
    ],
    # 20. Galaxy S24 Ultra screen black, won't turn on but phone rings
    20: [
        "Galaxy S24 Ultra display is completely black and won't turn on even though phone rings and works.",
        "My S24 Ultra screen is dead black, but device vibrates, rings, and has power with no damage.",
        "s24 ultra screen black wont turn on phone rings powers on no physical damage",
        "Samsung Galaxy S24 Ultra black screen phone working ringing sound no damage",
        "My Galaxy S24 Ultra rings and vibrates but the screen is totally black and won't show anything!",
        "How to fix black screen of death on Galaxy S24 Ultra when phone is still on and ringing?",
        "Galaxy S24 Ultra has no display output but still powers on and rings.",
        "Galaxy S24 Ultra screen unlit phone rings incoming calls sound active display dark",
        "Screen black on S24 Ultra device active and ringing but no image on display",
    ],
}


class QueryVariationGenerator:
    """Generates 8-10 deterministic, multi-register variations for troubleshooting queries."""

    def __init__(self, official_variations: Optional[Dict[int, List[str]]] = None):
        self.official_variations = (
            _OFFICIAL_QUERY_VARIATIONS
            if official_variations is None
            else official_variations
        )

    def generate_variations(self, query: str, query_index: Optional[int] = None) -> List[str]:
        """Generates 8-10 unique, deterministic query variations for a given query.
        
        Guarantees:
        - Exactly 8 to 10 variations returned.
        - All variations are non-empty strings.
        - Strictly deduplicated (case- and punctuation-insensitive).
        - Preserves original symptom intent.
        """
        # If query_index is provided and valid, use the curated official set
        if query_index is not None and query_index in self.official_variations:
            return self._finalize_variations(query, self.official_variations[query_index])

        # Try matching by normalized canonical query text
        norm = normalize_query_text(query).lower()
        matched_idx = self._find_matching_official_index(norm)
        if matched_idx is not None:
            return self._finalize_variations(query, self.official_variations[matched_idx])

        # Fallback: rule-based variation generator for unseen queries
        return self._generate_rule_based_variations(query)

    def _find_matching_official_index(self, norm_query: str) -> Optional[int]:
        """Finds if a query corresponds to one of the 20 official benchmark queries."""
        # Keyword fingerprinting for each of the 20 official queries
        # Give distinctive details more weight than common words such as
        # "screen", "black", or a shared Galaxy model name. This keeps, for
        # example, the three Flip 7 cases from matching one another.
        fingerprints = {
            1: ("a115g", "gmail", "tablet", "email"),
            2: ("s22", "white", "stock price", "smart tutor"),
            3: ("flip 7", "smart switch", "transfer my data"),
            4: ("a15/a16", "month", "black", "turn it on"),
            5: ("qr code", "smart switch", "tablet", "s25"),
            6: ("three app icons", "tablet", "dark", "won't open"),
            7: ("small", "full size", "main screen", "display"),
            8: ("flip 7", "inner screen", "outer cover screen", "touch"),
            9: ("flip 6", "flickers", "open it", "settings"),
            10: ("flip 6", "half black", "one side", "other side"),
            11: ("s25", "floating circle", "shortcuts", "remove it"),
            12: ("s22", "carrier", "activation message", "blank"),
            13: ("completely cracked", "total crack", "can't use"),
            14: ("s26 ultra", "tiny text", "blue", "holding the power"),
            15: ("s***** ultra", "milliseconds", "charger", "flashes"),
            16: ("s24", "occasional scrolling", "smart switch", "dark screen"),
            17: ("flip 7", "cracked again", "touch", "folds"),
            18: ("a17", "distorted", "diagnostic"),
            19: ("s22", "inputs are delayed", "laggy", "touch responsiveness"),
            20: ("s24 ultra", "rings", "no physical damage", "completely black"),
        }

        # Prefer the strongest matching fingerprint. Requiring multiple
        # distinctive terms avoids classifying short or unrelated queries.
        ranked = [
            (sum(1 for phrase in phrases if phrase in norm_query), index)
            for index, phrases in fingerprints.items()
        ]
        score, index = max(ranked, default=(0, 0))
        return index if score >= 2 else None

    def _generate_rule_based_variations(self, query: str) -> List[str]:
        """Generates deterministic variations for arbitrary/unseen queries."""
        clean = normalize_query_text(query)
        if not clean.split():
            clean = "Samsung device issue"
        words = clean.split()

        variations = [
            f"Samsung troubleshooting: {clean}",
            f"How do I fix when {clean.lower()}?",
            f"My device is having an issue where {clean.lower()}.",
            f"Help needed: {clean}",
            f"Galaxy phone problem: {clean.lower()}",
            f"{clean} - looking for troubleshooting steps",
            f"Why does {clean.lower()} on my Samsung device?",
            f"Samsung Galaxy error: {' '.join(words[:6])} issue",
            f"Troubleshoot {' '.join(words[:5])} on Galaxy device",
        ]
        return self._finalize_variations(query, variations)

    def _finalize_variations(self, original_query: str, candidates: List[str]) -> List[str]:
        """Ensures deduplication, proper count (8-10), and absence of original query."""
        orig_norm = _variation_key(normalize_query_text(original_query))
        seen = {orig_norm} if orig_norm else set()
        final: List[str] = []

        for c in candidates:
            c_clean = normalize_query_text(c)
            c_norm = _variation_key(c_clean)
            if c_clean and c_norm not in seen:
                seen.add(c_norm)
                final.append(c_clean)
            if len(final) == 10:
                break

        # Keep the documented 8-10 guarantee even for custom/short candidate
        # lists. These deterministic forms restate the supplied symptom
        # without inventing a new one.
        seed = normalize_query_text(original_query) or "Samsung device issue"
        templates = [
            f"How can I troubleshoot {seed}?",
            f"Samsung device problem: {seed}",
            f"Galaxy troubleshooting help for {seed}",
            f"What should I do when {seed}?",
            f"Help me resolve this Samsung issue: {seed}",
            f"Troubleshoot this device symptom: {seed}",
            f"Samsung support question about {seed}",
            f"My Galaxy needs help with this issue: {seed}",
            f"Steps to address this device problem: {seed}",
            f"Please help fix this Samsung symptom: {seed}",
        ]
        for candidate in templates:
            if len(final) >= 8:
                break
            cleaned = normalize_query_text(candidate)
            key = _variation_key(cleaned)
            if cleaned and key not in seen:
                seen.add(key)
                final.append(cleaned)

        return final[:10]

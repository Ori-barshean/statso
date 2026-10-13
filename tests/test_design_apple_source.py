"""Source contracts for touch fields, Safari surfaces, and mouse-only hover."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parent.parent
HOVER_QUERY = "@media (hover: hover) and (pointer: fine)"
COARSE_QUERY = "@media (pointer: coarse)"
NO_BLUR = "@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))"
LESS_TRANSPARENCY = "@media (prefers-reduced-transparency: reduce)"
REDUCED_MOTION = "@media (prefers-reduced-motion: reduce)"
HOVER_ALLOWED_OUTSIDE = frozenset()
CARD_TRANSITION = (
    "transition: transform 200ms var(--ease-out), box-shadow 200ms var(--ease-out), "
    "border-color 200ms var(--ease-out);"
)


def rules(css):
    """Read flat style rules and their enclosing at-rules, including print @page."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    stack, result, start = [], [], 0
    for match in re.finditer(r"[{}]", css):
        if match.group() == "{":
            if stack and not stack[-1][0].startswith("@"):
                raise ValueError("Nested block inside a style rule")
            prelude = " ".join(css[start:match.start()].split())
            stack.append((prelude, match.end(), start))
        else:
            if not stack:
                raise ValueError("Unbalanced closing brace")
            prelude, body_start, offset = stack.pop()
            if not prelude.startswith("@"):
                result.append((prelude, css[body_start:match.start()],
                               tuple(item[0] for item in stack), offset))
        start = match.end()
    if stack:
        raise ValueError("Unclosed block")
    return result


def parts(selector):
    """Split a selector list without splitting functional or attribute selectors."""
    result, start, depth = [], 0, 0
    for index, char in enumerate(selector):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(selector[start:index].strip())
            start = index + 1
    result.append(selector[start:].strip())
    return result


def is_text_field(part):
    while re.search(r"\([^()]*\)", part):
        part = re.sub(r"\([^()]*\)", "", part)
    compound = re.split(r"[\s>+~]+", part.strip())[-1]
    return bool(re.match(r"(?:input|select|textarea)(?![\w-])", compound)
                and not re.search(
                    r"\[type\s*=\s*['\"]?(?:checkbox|radio|range|button|submit|reset|file|color|image|hidden)['\"]?\s*\]",
                    compound, re.I))


def values(body, property_name):
    return [value.strip() for value in re.findall(
        r"(?<![-\w])" + re.escape(property_name) + r"\s*:\s*([^;]+)", body)]


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_head = False
        self.themes, self.headings = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "head":
            self.in_head = True
        if tag == "meta" and attrs.get("name") == "theme-color":
            self.themes.append((attrs.get("content"), self.in_head))
        if tag == "h1":
            self.headings.append(attrs)

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False


class AppleDesignSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (ROOT / "assets/statso.css").read_text(encoding="utf-8")
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.rules = rules(cls.css)

    def test_every_hover_rule_is_inside_the_mouse_only_query(self):
        hover = [rule for rule in self.rules if ":hover" in rule[0]]
        self.assertGreaterEqual(len(hover), 18)
        for selector, body, context, offset in hover:
            with self.subTest(selector=selector):
                if selector not in HOVER_ALLOWED_OUTSIDE:
                    self.assertIn(HOVER_QUERY, context)

    def test_the_mouse_only_query_holds_only_hover_rules(self):
        for selector, body, context, offset in self.rules:
            if HOVER_QUERY in context:
                for part in parts(selector):
                    self.assertIn(":hover", part)

    def test_focus_and_script_states_stay_outside_every_query(self):
        for target in ('.nav-group[data-open="true"] .nav-submenu',
                       '.nav-group[data-closed="true"] .nav-submenu'):
            matches = [rule for rule in self.rules if rule[0] == target]
            self.assertTrue(matches, target)
            for selector, body, context, offset in matches:
                self.assertEqual(context, (), selector)
                if "data-closed" in selector:
                    self.assertIn("!important", body)
        focus = [rule for rule in self.rules
                 if rule[0].startswith(":is(") and rule[0].endswith(":focus-visible")]
        self.assertTrue(focus)
        for selector, body, context, offset in focus:
            self.assertEqual(context, (), selector)

    def test_overrides_still_follow_the_hover_rule_they_beat(self):
        for earlier, later in (
                (".guide-card:hover", ".guide-card-soon:hover"),
                (".nav-item:hover", '.nav-item[aria-current="page"]'),
                (".lang-choice:hover", '.lang-choice[aria-current="true"]')):
            before = [r[3] for r in self.rules if r[0] == earlier]
            after = [r[3] for r in self.rules if r[0] == later]
            self.assertTrue(before, earlier)
            self.assertTrue(after, later)
            self.assertLess(max(before), min(after))

    def test_text_fields_are_at_least_16px_on_touch_screens(self):
        covering = [r for r in self.rules if COARSE_QUERY in r[2]
                    and "max(16px, 1rem)" in values(r[1], "font-size")
                    and {"select", "textarea"}.issubset(parts(r[0]))
                    and any(p.startswith("input") and is_text_field(p) for p in parts(r[0]))]
        self.assertTrue(covering, "Missing the touch text-field font rule")
        for selector, body, context, offset in self.rules:
            fields = [p for p in parts(selector) if is_text_field(p)]
            if not fields:
                continue
            sizes = values(body, "font-size")
            if COARSE_QUERY in context:
                for size in sizes:
                    pixels = re.fullmatch(r"(\d+(?:\.\d+)?)px", size)
                    self.assertTrue(size == "max(16px, 1rem)" or
                                    (pixels and float(pixels[1]) >= 16), (selector, size))
            elif sizes or any(v != "inherit" for v in values(body, "font")):
                for field in fields:
                    self.assertTrue(any(field in parts(r[0]) and offset < r[3] for r in covering),
                                    f"Repeat {field} after its font rule in the coarse query")

    def test_every_backdrop_filter_has_its_webkit_twin(self):
        active = []
        for selector, body, context, offset in self.rules:
            standard = values(body, "backdrop-filter")
            prefixed = values(body, "-webkit-backdrop-filter")
            with self.subTest(selector=selector, context=context):
                self.assertEqual(sorted(standard), sorted(prefixed))
            active.extend(value for value in standard if value != "none")
        self.assertTrue(active)

    def test_every_blurred_surface_has_an_opaque_fallback(self):
        blurred = {part for selector, body, context, offset in self.rules
                   if any("blur(" in v for prop in ("backdrop-filter", "-webkit-backdrop-filter")
                          for v in values(body, prop)) for part in parts(selector)}
        self.assertTrue(blurred)
        for part in blurred:
            for query in (NO_BLUR, LESS_TRANSPARENCY):
                fallback = [r for r in self.rules if query in r[2] and part in parts(r[0])
                            and any(v in ("#fff", "#ffffff", "white", "var(--surface)")
                                    for v in values(r[1], "background"))]
                self.assertTrue(fallback, (part, query))
                if query == LESS_TRANSPARENCY:
                    self.assertTrue(any(values(r[1], "backdrop-filter") == ["none"] and
                                        values(r[1], "-webkit-backdrop-filter") == ["none"]
                                        for r in fallback), part)

    def test_the_header_keeps_its_translucent_white(self):
        headers = [r for r in self.rules if r[0] == ".site-header" and not r[2]]
        self.assertEqual(len(headers), 1)
        body = headers[0][1]
        self.assertEqual(values(body, "background"), ["rgba(255,255,255,.94)"])
        for prop in ("backdrop-filter", "-webkit-backdrop-filter"):
            self.assertEqual(values(body, prop), ["blur(20px) saturate(180%)"])

    def test_theme_color_matches_the_page_wash(self):
        markup = Markup()
        markup.feed(self.html)
        wash = [v for selector, body, context, offset in self.rules if selector == ":root"
                for v in values(body, "--wash")]
        self.assertEqual(len(wash), 1)
        self.assertEqual(markup.themes, [(wash[0], True)])

    def test_no_h1_is_styled_as_an_eyebrow(self):
        for path in [ROOT / "index.html", *sorted((ROOT / "assets").glob("statso-*.js"))]:
            source = path.read_text(encoding="utf-8")
            for tag in re.findall(r"<h1\b[^>]*>", source, re.I):
                markup = Markup()
                markup.feed(tag)
                for attrs in markup.headings:
                    self.assertNotIn("eyebrow", attrs.get("class", "").split(), str(path))
        self.assertIn('<h1 id="page-title">תמונת מצב עדכנית</h1>', self.html)

    def test_every_transition_is_cancelled_under_reduced_motion(self):
        animated, cancelled = set(), set()
        for selector, body, context, offset in self.rules:
            transitions = values(body, "transition")
            if REDUCED_MOTION in context and "none" in transitions:
                cancelled.update(parts(selector))
            elif REDUCED_MOTION not in context and any(v != "none" for v in transitions):
                animated.update(parts(selector))
        self.assertGreaterEqual(len(animated), 5)
        self.assertLessEqual(animated, cancelled)

    def test_cards_share_the_ease_out_curve(self):
        roots = [r for r in self.rules if r[0] == ":root" and not r[2]]
        self.assertTrue(any("--ease-out: cubic-bezier(.23, 1, .32, 1);" in r[1] for r in roots))
        for card in (".tool-card", ".guide-card"):
            matches = [r for r in self.rules if r[0] == card and not r[2]]
            self.assertEqual(len(matches), 1)
            self.assertIn(CARD_TRANSITION, matches[0][1])


if __name__ == "__main__":
    unittest.main()

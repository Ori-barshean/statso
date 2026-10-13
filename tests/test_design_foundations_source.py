"""Source contracts for the shared design foundations and their contrast pairs."""
from pathlib import Path
import re
import unittest

from tests.test_design_apple_source import rules, parts, values


ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "assets/statso.css").read_text(encoding="utf-8")
HOVER = ("@media (hover: hover) and (pointer: fine)",)
FORCED = ("@media (forced-colors: active)",)
FOCUS = ':is(a, button, summary, input, select, textarea, [tabindex]:not([tabindex="-1"])):focus-visible'
CURRENT = '.nav-item[aria-current="page"]'
PALETTE = {
    "--ink": "#1d1d1f", "--muted": "#6e6e73", "--line": "#e5e5ea",
    "--field-border": "#86868b", "--surface": "#ffffff", "--wash": "#f5f5f7",
    "--navy": "#172e55", "--blue": "#0071e3", "--link": "#0066cc",
    "--blue-tint": "#e8f2fc", "--blue-tint-soft": "#f0f6fd",
    "--cyan": "#0891b2", "--violet": "#7c3aed", "--orange": "#ea580c",
}
TIERS = {
    "control": (
        ".nav-item", "input, select, textarea", ".nav-submenu a", ".lang-button",
        ".lang-choice", ".btn-ghost", ".guide-notice button, .copy-url",
        ".guide-mcode-button", ".contact-submit", ".skip-link", ".code-block pre", "#mc-copy",
    ),
    "group": (
        ".data-problem", ".date-group", ".calc-output", ".nav-submenu", ".lang-menu",
        ".rent-block", ".rent-summary-grid > div", ".table-scroll", ".guide-selectors fieldset",
        ".guide-note, .guide-notice", ".step-art figure", ".contact-status",
        ".timeline-figure", ".mcode-form fieldset",
    ),
    "card": (".kpi-card, .panel", ".tool-card", ".guide-card", ".guide-steps > li", ".prose-guide > section"),
}


def rule(selector, context=()):
    """Require a unique rule with this exact normalized selector and context."""
    selector = " ".join(selector.split())
    matches = [body for name, body, enclosing, _ in rules(CSS)
               if name == selector and enclosing == context]
    if len(matches) != 1:
        raise AssertionError((selector, context, len(matches)))
    return matches[0]


def tokens():
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", rule(":root")))


def resolve(value):
    """Resolve opaque solid colours; transparent or contextual paints need a pair."""
    value = value.strip()
    variable = re.fullmatch(r"var\((--[\w-]+)\)", value)
    if variable:
        value = tokens().get(variable[1], "")
    value = value.lower()
    if value in ("white", "#fff"):
        return "#ffffff"
    if re.fullmatch(r"#[0-9a-f]{6}", value):
        return value
    rgba = re.fullmatch(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([.\d]+)\)", value)
    if rgba and float(rgba[4]) == 1:
        return tuple(float(rgba[i]) for i in (1, 2, 3))
    return None


def channels(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) if isinstance(color, str) else color


def composite(rgba, background):
    match = re.fullmatch(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([.\d]+)\)", rgba)
    if not match:
        raise AssertionError(rgba)
    alpha = float(match[4])
    return tuple(float(match[i + 1]) * alpha + c * (1 - alpha)
                 for i, c in enumerate(channels(background)))


def contrast(first, second):
    def luminance(color):
        srgb = [c / 255 for c in channels(color)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in srgb]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    a, b = luminance(first), luminance(second)
    return (max(a, b) + .05) / (min(a, b) + .05)


def paint(selector, property_name, context=()):
    return resolve(values(rule(selector, context), property_name)[-1])


def excluded(selector, context):
    return "print" in selector or "@media print" in context or FORCED[0] in context


def text_pairs():
    """All text pairs checked below, also usable to report the sub-5:1 margins."""
    for name in ("ink", "muted", "link", "navy"):
        for background in ("#ffffff", "var(--wash)"):
            yield f"--{name} on {background}", resolve(f"var(--{name})"), resolve(background)
    for selector, body, context, _ in rules(CSS):
        if excluded(selector, context):
            continue
        foregrounds, backgrounds = values(body, "color"), values(body, "background")
        if foregrounds and backgrounds:
            foreground, background = resolve(foregrounds[-1]), resolve(backgrounds[-1])
            if foreground is not None and background is not None:
                yield selector, foreground, background
    cross = [
        (".data-table thead th", '.table-wrap[role="region"] thead th'),
        (".data-table thead th", "th"),
        *((selector, ".calc-output") for selector in (
            ".calc-result span", ".calc-result small", ".calc-note",
            ".calc-output .result-disclaimer", ".calc-output .inline-error")),
        (".contact-submit", ".contact-submit:hover"),
        (".guide-mcode-button", ".guide-mcode-button:hover"),
        (".rent-summary-highlight span", ".rent-summary-highlight"),
        ("label", ".date-group"),
        (".guide-card small", ".guide-card-soon"),
        (".step-art figcaption", ".step-art figure"),
        (".timeline-figure figcaption", ".timeline-figure"),
        (".footer-links a", "html"),
        (".footer-links a:hover", "html"),
    ]
    for foreground, background in cross:
        yield (f"{foreground} on {background}",
               paint(foreground, "color", HOVER if ":hover" in foreground else ()),
               paint(background, "background", HOVER if ":hover" in background else ()))
    for background in ("--wash", "--navy"):
        yield (f".nav-item on header over {background}", paint(".nav-item", "color"),
               composite(values(rule(".site-header"), "background")[-1], tokens()[background]))


class DesignFoundationsSourceTests(unittest.TestCase):
    def test_palette_tokens_have_the_approved_values(self):
        actual = tokens()
        for name, value in PALETTE.items():
            with self.subTest(token=name):
                self.assertEqual(actual.get(name), value)
        for tier, size in (("control", "10px"), ("group", "14px"), ("card", "20px")):
            self.assertEqual(actual.get(f"--r-{tier}"), size)
        self.assertNotIn("--radius", CSS)

    def test_no_legacy_colour_outside_print(self):
        denied = r"#(?:2563eb|1d4ed8|eef4ff|e8f0ff|f5f8ff|f0f5ff|eef3f9|f8fbff|f8fafc|d5dde8|a9c3f8|cbd5e1)\b"
        for selector, body, context, _ in rules(CSS):
            if selector != ":root" and "print" not in selector and "@media print" not in context:
                with self.subTest(selector=selector):
                    self.assertIsNone(re.search(denied, body, re.I))
        self.assertNotRegex(CSS.lower(), r"rgba\(\s*(?:37\s*,\s*99\s*,\s*235|30\s*,\s*50\s*,\s*80)|radial-gradient")
        chart = (ROOT / "assets/statso-chart.js").read_text(encoding="utf-8")
        self.assertNotRegex(chart.lower(), r"#2563eb|rgba\(\s*37\s*,\s*99\s*,\s*235")

    def test_blue_is_never_a_text_colour(self):
        self.assertNotRegex(CSS, r"(?<![-\w])color\s*:\s*var\(--blue\)")
        selectors = (
            CURRENT, ".eyebrow", ".section-toggle:hover .toggle-caret", ".nav-submenu a:hover",
            ".lang-button:hover", ".lang-choice:hover", '.lang-choice[aria-current="true"]',
            ".tool-back:hover", ".btn-ghost:hover:not(:disabled)", ".btn-copy", ".footer-links a:hover",
            ".guide-card b", ".guide-back", ".guide-pill:hover", ".guide-copy-pill.copy-url:hover",
            ".step-copy h2", ".info-back", ".contact-disclosure a", ".chart-alt a",
        )
        for selector in selectors:
            with self.subTest(selector=selector):
                self.assertEqual(values(rule(selector, HOVER if ":hover" in selector else ()), "color"), ["var(--link)"])

    def test_text_pairs_meet_aa_contrast(self):
        for label, foreground, background in text_pairs():
            with self.subTest(pair=label):
                self.assertIsNotNone(foreground)
                self.assertIsNotNone(background)
                self.assertGreaterEqual(contrast(foreground, background), 4.5)

    def test_non_text_colours_and_blue_button_text_meet_contrast(self):
        for name in ("--field-border", "--blue"):
            for background in ("#ffffff", tokens()["--wash"]):
                with self.subTest(token=name, background=background):
                    self.assertGreaterEqual(contrast(tokens()[name], background), 3)
        outline = re.fullmatch(r"3px solid (.+)", values(rule(FOCUS), "outline")[-1])[1]
        self.assertEqual(outline, "var(--link)")
        for background in ("#ffffff", tokens()["--wash"], tokens()["--blue-tint"]):
            self.assertGreaterEqual(contrast(resolve(outline), background), 3)
        self.assertGreaterEqual(contrast(tokens()["--link"], tokens()["--blue-tint"]), 3)
        for background in (tokens()["--blue"], "#0058b9"):
            self.assertGreaterEqual(contrast("#ffffff", background), 4.5)

    def test_radii_only_use_tokens_or_approved_shapes(self):
        allowed = {"var(--r-control)", "var(--r-group)", "var(--r-card)", "0", "50%", "999px", "28%"}
        for selector, body, context, _ in rules(CSS):
            if selector == ":root":
                continue
            for radius in re.findall(r"(?<![-\w])border(?:-[\w-]+)?-radius\s*:\s*([^;]+)", body):
                with self.subTest(selector=selector, radius=radius):
                    self.assertLessEqual(set(radius.replace("/", " ").split()), allowed)

    def test_each_component_uses_its_radius_tier(self):
        for tier, selectors in TIERS.items():
            for selector in selectors:
                with self.subTest(selector=selector):
                    self.assertEqual(values(rule(selector), "border-radius"), [f"var(--r-{tier})"])
        for selector in (".brand-mark", ".kpi-brand .brand-mark", ".tool-card-mark", ".toggle-caret"):
            self.assertEqual(values(rule(selector), "border-radius"), ["28%"])
        for selector, radius in (
                (".kpi-card::before", "var(--r-card) var(--r-card) 0 0"),
                (".url-block code", "var(--r-control) 0 0 var(--r-control)"),
                (".url-block .copy-url", "0 var(--r-control) var(--r-control) 0")):
            self.assertEqual(values(rule(selector), "border-radius"), [radius])

    def test_inner_radius_never_exceeds_its_container(self):
        ranks = {"var(--r-control)": 1, "var(--r-group)": 2, "var(--r-card)": 3, "0": 0}
        pairs = (
            (".kpi-card, .panel", ".kpi-card::before"),
            (".kpi-card, .panel", ".date-group"),
            (".kpi-card, .panel", ".calc-output"),
            (".kpi-card, .panel", ".rent-block"),
            (".kpi-card, .panel", ".rent-summary-grid > div"),
            (".kpi-card, .panel", ".table-scroll"),
            (".date-group", "input, select, textarea"),
            (".rent-block", "input, select, textarea"),
            (".nav-submenu", ".nav-submenu a"),
            (".lang-menu", ".lang-choice"),
            (".guide-selectors fieldset", "input, select, textarea"),
            (".mcode-form fieldset", "input, select, textarea"),
            (".guide-note, .guide-notice", ".guide-notice button, .copy-url"),
            (".guide-steps > li", ".step-art figure"),
            (".guide-steps > li", ".url-block code"),
            (".guide-steps > li", ".url-block .copy-url"),
            (".prose-guide > section", ".timeline-figure"),
        )
        for outer, inner in pairs:
            with self.subTest(outer=outer, inner=inner):
                outer_ranks = [ranks[v] for v in values(rule(outer), "border-radius")[-1].split()]
                inner_ranks = [ranks[v] for v in values(rule(inner), "border-radius")[-1].split()]
                self.assertLessEqual(max(inner_ranks), max(outer_ranks))

    def test_cards_share_one_shadow_token(self):
        self.assertEqual(tokens()["--shadow-card"], "0 1px 2px rgba(0,0,0,.04), 0 6px 20px rgba(0,0,0,.05)")
        self.assertEqual(tokens()["--shadow-menu"], "0 12px 32px rgba(0,0,0,.12)")
        expected = {selector: "var(--shadow-card)" for selector in TIERS["card"]}
        expected.update({selector: "var(--shadow-menu)" for selector in (".nav-submenu", ".lang-menu")})
        for selector, shadow in expected.items():
            self.assertEqual(values(rule(selector), "box-shadow"), [shadow])
        for selector, body, context, _ in rules(CSS):
            for shadow in values(body, "box-shadow"):
                if selector in expected and not context:
                    continue
                if selector == ".tool-card:hover" and context == HOVER:
                    self.assertEqual(shadow, "0 2px 4px rgba(0,0,0,.05), 0 12px 32px rgba(0,0,0,.10)")
                else:
                    self.assertTrue(shadow in ("none", "0 0 0 2px #fff") or shadow.startswith("inset "), (selector, shadow))

    def test_hebrew_tracking_is_gentler(self):
        for selector, base, hebrew in (
                (".eyebrow", ".08em", "0"), (".hero h1", "-.03em", "-.02em"),
                (".kpi-value, .kpi-date", "-.025em", "-.015em"),
                (".guide-hero h1, .guide-header h1", "-.025em", "-.015em"),
                (".info-header h1", "-.025em", "-.015em")):
            translated = ", ".join('html[lang="he"] ' + part for part in parts(selector))
            with self.subTest(selector=selector):
                self.assertEqual(values(rule(selector), "letter-spacing"), [base])
                self.assertEqual(values(rule(translated), "letter-spacing"), [hebrew])
                parsed = rules(CSS)
                base_index = next(i for i, r in enumerate(parsed) if r[0] == selector and not r[2])
                self.assertEqual(parsed[base_index + 1][0], translated)
        self.assertEqual(values(rule(".eyebrow"), "text-transform"), ["uppercase"])
        for selector, body, context, _ in rules(CSS):
            for spacing in values(body, "letter-spacing"):
                self.assertGreaterEqual(float(spacing.removesuffix("em")), -.03, selector)

    def test_page_and_footer_use_the_flat_wash(self):
        self.assertEqual(values(rule("body"), "background"), ["var(--wash)"])
        self.assertEqual(values(rule("footer"), "background"), ["transparent"])
        self.assertEqual(values(rule("footer"), "border-top"), ["1px solid var(--line)"])

    def test_current_navigation_has_one_non_colour_bar(self):
        body = rule(CURRENT)
        for prop, value in (("position", "relative"), ("color", "var(--link)"), ("background", "var(--blue-tint)")):
            self.assertEqual(values(body, prop), [value])
        self.assertFalse(values(body, "box-shadow"))
        after = rule(CURRENT + "::after")
        declarations = [tuple(d.strip().split(":", 1)) for d in after.split(";") if d.strip()]
        expected = {"content": '""', "position": "absolute", "inset-inline": "12px", "inset-block-end": "4px",
                    "height": "2px", "border-radius": "999px", "background": "currentColor"}
        self.assertEqual(len(declarations), len(expected))
        self.assertEqual({key: value.strip() for key, value in declarations}, expected)
        self.assertEqual(values(rule(CURRENT + "::after", FORCED), "display"), ["none"])
        self.assertEqual(values(rule(CURRENT, FORCED), "border-block-end"), ["3px solid CanvasText"])
        self.assertEqual(CSS.count(FORCED[0]), 1)
        self.assertEqual(rules(CSS)[-1][2], FORCED)

    def test_focused_nav_item_paints_above_its_neighbours(self):
        # the current item is position: relative (for its bar); without a lifted focused item its tint would cover
        # the 3px focus ring of a neighbour on the side that faces it (nav gap is only 2-3px at narrow widths)
        body = rule(".nav-item:focus-visible")
        self.assertEqual(values(body, "position"), ["relative"])
        self.assertEqual(values(body, "z-index"), ["1"])

    def test_chart_cpi_uses_the_new_blue(self):
        chart = (ROOT / "assets/statso-chart.js").read_text(encoding="utf-8")
        dataset = re.search(r"const datasets = \[\{(.*?)\}\];", chart, re.S)[1]
        border = re.search(r"borderColor: '([^']+)'", dataset)[1]
        fill = re.search(r"backgroundColor: '([^']+)'", dataset)[1]
        self.assertEqual(border, tokens()["--blue"])
        self.assertEqual(fill, "rgba(" + ",".join(str(c) for c in channels(border)) + ",.1)")
        self.assertGreaterEqual(contrast(border, "#ffffff"), 3)
        self.assertGreaterEqual(contrast(border, composite(fill, "#ffffff")), 3)
        self.assertIn("borderColor: '#16a34a'", chart)
        self.assertIn("backgroundColor: 'rgba(22,163,74,.1)'", chart)
        self.assertRegex(chart, r"EVENT_COLOR\s*=\s*'#c2410c'")

    def test_404_uses_the_new_palette(self):
        html = (ROOT / "404.html").read_text(encoding="utf-8")
        css = re.search(r"<style>(.*?)</style>", html, re.S)[1]
        bodies = {selector: body for selector, body, context, _ in rules(css) if not context}
        for selector, prop, value in (
                ("body", "color", "#1d1d1f"), ("body", "background", "#ffffff"),
                ("h1, h2", "color", "#1d1d1f"), ("a", "color", "#0066cc"),
                ("section + section", "border-top", "1px solid #86868b"),
                ("a:focus-visible", "outline", "3px solid #0066cc")):
            self.assertEqual(values(bodies[selector], prop), [value])
        self.assertNotRegex(html.lower(), r"#182230|#1d4ed8|#74839a")

    def test_card_and_group_paddings_sit_on_the_grid(self):
        for selector, padding in (
                (".kpi-card", "24px"), (".tool-card", "24px"), (".guide-card", "24px"),
                (".tool-page", "28px"), (".guide-selectors fieldset", "16px"),
                (".mcode-form fieldset", "20px"), (".rent-block", "16px 20px")):
            with self.subTest(selector=selector):
                self.assertEqual(values(rule(selector), "padding"), [padding])
        self.assertEqual(values(rule(".rent-grid"), "grid-template-columns"),
                         ["repeat(auto-fit, minmax(min(100%, 190px), 1fr))"])


if __name__ == "__main__":
    unittest.main()

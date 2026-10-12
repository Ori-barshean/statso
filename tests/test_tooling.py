"""Regression checks for test groups, the pre-push hook and statement review tooling."""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import run_tests, update_statement_date
from scripts.statement_fingerprint import TIME_RE, accessibility_page, fingerprint

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / '.githooks' / 'pre-push'


def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test


class TestGroupTests(unittest.TestCase):
    def test_every_test_file_belongs_to_exactly_one_group(self):
        self.assertEqual(run_tests.classification_problems(), [])

    def test_all_is_data_plus_site(self):
        self.assertEqual(run_tests.GROUPS['all'], run_tests.DATA_TESTS + run_tests.SITE_TESTS)

    def test_data_suite_loads_only_data_modules(self):
        modules = {test.id().split('.')[1] for test in flatten(run_tests.build_suite(run_tests.DATA_TESTS))}
        self.assertEqual(modules, {name[:-3] for name in run_tests.DATA_TESTS})

    def test_exit_code_follows_the_result(self):
        def fail():
            raise AssertionError('expected failure')

        for suite, expected in ((unittest.FunctionTestCase(lambda: None), 0),
                                (unittest.FunctionTestCase(fail), 1),
                                (unittest.TestSuite(), 1)):
            with self.subTest(expected=expected):
                self.assertEqual(run_tests.run_suite(suite, stream=io.StringIO()), expected)

    def test_unknown_group_and_missing_file_fail(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            run_tests.main(['--group', 'nope'])
        self.assertEqual(raised.exception.code, 2)
        stderr = io.StringIO()
        with mock.patch.dict(run_tests.GROUPS, {'data': ('test_does_not_exist.py',)}), redirect_stderr(stderr):
            self.assertEqual(run_tests.main(['--group', 'data']), 1)
        self.assertIn('test_does_not_exist.py', stderr.getvalue())


@unittest.skipIf(shutil.which('git') is None, 'git is required for hook checks')
class PrePushHookTests(unittest.TestCase):
    def test_hook_file(self):
        self.assertTrue(HOOK.is_file())
        self.assertTrue(os.access(HOOK, os.X_OK))
        source = HOOK.read_bytes()
        self.assertTrue(source.startswith(b'#!/bin/sh\n'))
        self.assertNotIn(b'\r', source)
        text = source.decode('utf-8')
        for command in ('git rev-parse --show-toplevel',
                        'python3 -m unittest discover -s tests -t .', 'git push --no-verify'):
            self.assertIn(command, text)
        self.assertNotIn('--group', text)
        self.assertRegex(text, r'[א-ת]')

    def run_hook(self, exit_code):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / 'repo'
            repo.mkdir()
            sub = repo / 'sub'
            sub.mkdir()
            env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
            subprocess.run(['git', 'init', '-q', str(repo)], env=env, check=True, capture_output=True)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            stub = bin_dir / 'python3'
            stub.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$@" > "$STUB_LOG"\nexit "$STUB_EXIT"\n')
            stub.chmod(0o755)
            log = root / 'stub.log'
            env.update(PATH=str(bin_dir) + os.pathsep + env.get('PATH', ''),
                       STUB_LOG=str(log), STUB_EXIT=str(exit_code))
            result = subprocess.run([str(HOOK), 'origin', 'https://example.invalid/statso.git'],
                                    cwd=sub, env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, encoding='utf-8')
            lines = log.read_text().splitlines()
            self.assertEqual(Path(lines[0]).resolve(), repo.resolve())
            self.assertEqual(lines[1:], ['-m', 'unittest', 'discover', '-s', 'tests', '-t', '.'])
            return result

    def test_failing_suite_aborts_the_push(self):
        result = self.run_hook(1)
        self.assertEqual(result.returncode, 1)
        self.assertIn('--no-verify', result.stderr)
        self.assertIn('python3 -m unittest discover -s tests -t .', result.stderr)

    def test_passing_suite_allows_the_push(self):
        self.assertEqual(self.run_hook(0).returncode, 0)


class StatementDateScriptTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.html_path = self.root / update_statement_date.HTML_FILE
        self.guard_path = self.root / update_statement_date.GUARD_FILE
        self.guard_path.parent.mkdir()
        for path in (self.html_path, self.guard_path):
            path.write_bytes((ROOT / path.relative_to(self.root)).read_bytes())
        self.before = self.contents()

    def contents(self):
        return self.html_path.read_bytes(), self.guard_path.read_bytes()

    def run_script(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = update_statement_date.main(['--root', str(self.root), *args])
        return result, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def constant(text, name):
        return re.search(r"^" + name + r" = '([^'\n]*)'$", text, re.M).group(1)

    def test_dry_run_writes_nothing(self):
        result, output, error = self.run_script('--date', '2020-02-03')
        self.assertEqual(result, 0, error)
        self.assertEqual(self.contents(), self.before)
        guard = self.before[1].decode('utf-8')
        for text in (self.constant(guard, 'STATEMENT_DATE'), '2020-02-03',
                     self.constant(guard, 'STATEMENT_FINGERPRINT'), '--reviewed',
                     'Every statement sentence must be supported by code, tests or a check actually performed.'):
            self.assertIn(text, output)

    def test_reviewed_rewrites_dates_and_constants(self):
        html, guard = (text.decode('utf-8') for text in self.before)
        page = accessibility_page(html)
        end = page.end() - len('</article>')
        mutated = html[:end] + '<p>tooling test</p>' + html[end:]
        self.assertNotEqual(fingerprint(mutated), self.constant(guard, 'STATEMENT_FINGERPRINT'))
        self.html_path.write_bytes(mutated.encode('utf-8'))
        result, output, error = self.run_script('--reviewed', '--date', '2020-02-03')
        self.assertEqual(result, 0, error)
        after, new_guard = (text.decode('utf-8') for text in self.contents())
        self.assertCountEqual(TIME_RE.findall(accessibility_page(after).group(0)),
                              [('2020-02-03', '3 בפברואר 2020'), ('2020-02-03', '3 February 2020')])
        self.assertEqual(TIME_RE.sub('', mutated), TIME_RE.sub('', after))
        self.assertEqual(self.constant(new_guard, 'STATEMENT_DATE'), '2020-02-03')
        self.assertEqual(self.constant(new_guard, 'STATEMENT_FINGERPRINT'), fingerprint(after))
        constants = r"^STATEMENT_(?:DATE|FINGERPRINT) = '[^'\n]*'$"
        self.assertEqual(re.sub(constants, '', guard, flags=re.M),
                         re.sub(constants, '', new_guard, flags=re.M))
        self.assertIn('index.html changed', output)
        self.assertIn('rebuild the offline file', output)
        self.assertIn('python3 -m scripts.build_offline', output)
        self.assertIn('~/Desktop/statso-test.html', output)

    def test_idempotent(self):
        self.assertEqual(self.run_script('--reviewed', '--date', '2020-02-03')[0], 0)
        before = self.contents()
        result, output, error = self.run_script('--reviewed', '--date', '2020-02-03')
        self.assertEqual(result, 0, error)
        self.assertEqual(self.contents(), before)
        self.assertIn('nothing to change', output)

    def test_month_names(self):
        he = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר']
        en = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
        for month in range(1, 13):
            with self.subTest(month=month):
                self.assertEqual(update_statement_date.visible_dates(date(2020, month, 1)),
                                 {'he': f'1 ב{he[month - 1]} 2020', 'en': f'1 {en[month - 1]} 2020'})

    def test_refuses_malformed_input(self):
        html, guard = (text.decode('utf-8') for text in self.before)
        elements = update_statement_date.time_elements(html)
        he, en = elements['he'], elements['en']
        cases = [
            ('missing he time', html[:he.start()] + html[he.end():], guard),
            ('duplicate en time', html[:en.end()] + en.group(0) + html[en.end():], guard),
            ('unexpected time attributes', html[:he.start()] + he.group(0).replace('<time ', '<time class="x" ') + html[he.end():], guard),
            ('missing article', html.replace('id="accessibility-page"', 'id="missing-page"'), guard),
            ('missing fingerprint', html, re.sub(r"^STATEMENT_FINGERPRINT = .*\n", '', guard, flags=re.M)),
            ('duplicate date', html, guard + "\nSTATEMENT_DATE = '2020-02-03'\n"),
        ]
        for label, bad_html, bad_guard in cases:
            with self.subTest(label=label):
                self.html_path.write_bytes(bad_html.encode('utf-8'))
                self.guard_path.write_bytes(bad_guard.encode('utf-8'))
                before = self.contents()
                result, output, error = self.run_script('--reviewed', '--date', '2020-02-03')
                self.assertEqual(result, 1)
                self.assertEqual(self.contents(), before)
                self.assertTrue(error.strip())

    def test_bad_date_rejected(self):
        for text in ('2026-13-01', '20261012', '2026-1-5', '2999-01-01'):
            with self.subTest(date=text):
                with self.assertRaises(SystemExit) as raised:
                    self.run_script('--reviewed', '--date', text)
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(self.contents(), self.before)

    def test_default_date_is_jerusalem_today(self):
        with mock.patch.object(update_statement_date, 'israel_today', return_value=date(2020, 2, 3)):
            result, output, error = self.run_script()
        self.assertEqual(result, 0, error)
        self.assertIn('2020-02-03', output)
        before = datetime.now(ZoneInfo('Asia/Jerusalem')).date()
        today = update_statement_date.israel_today()
        after = datetime.now(ZoneInfo('Asia/Jerusalem')).date()
        self.assertIn(today, {before, after})

    def test_module_entrypoint_dry_run(self):
        result = subprocess.run([sys.executable, '-m', 'scripts.update_statement_date',
                                 '--root', str(self.root), '--date', '2020-02-03'], cwd=ROOT,
                                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                                capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.contents(), self.before)
        self.assertIn('dry run: nothing written', result.stdout)

    def test_guard_messages_name_the_command(self):
        self.assertEqual(self.guard_path.read_text(encoding='utf-8').count(update_statement_date.COMMAND), 2)


if __name__ == '__main__':
    unittest.main()


class StatementScriptHardeningTests(unittest.TestCase):
    """Refusals and rollback found by the review: the script must not report success on a half-written or ambiguous state."""

    def setUp(self):
        import pathlib, shutil, tempfile
        self.root_dir = pathlib.Path(__file__).resolve().parent.parent
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / 'tests').mkdir()
        shutil.copy(self.root_dir / 'index.html', self.root / 'index.html')
        shutil.copy(self.root_dir / 'tests' / 'test_a11y_round8_source.py', self.root / 'tests' / 'test_a11y_round8_source.py')
        self.html = self.root / 'index.html'
        self.guard = self.root / 'tests' / 'test_a11y_round8_source.py'

    def run_script(self):
        import contextlib, io
        from scripts import update_statement_date
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = update_statement_date.main(['--root', str(self.root), '--reviewed', '--date', '2020-02-03'])
        return code, err.getvalue()

    def test_duplicate_constant_in_another_format_is_refused(self):
        for extra in ('\nSTATEMENT_DATE = "2026-10-12"\n', '\nif True:\n    STATEMENT_FINGERPRINT = \'x\'\n'):
            with self.subTest(extra=extra):
                before = (self.html.read_bytes(), self.guard.read_bytes())
                self.guard.write_bytes(before[1] + extra.encode('utf-8'))
                changed = self.guard.read_bytes()
                code, err = self.run_script()
                self.assertEqual(code, 1)
                self.assertTrue(err)
                self.assertEqual((self.html.read_bytes(), self.guard.read_bytes()), (before[0], changed))
                self.guard.write_bytes(before[1])

    def test_missing_closing_article_is_refused(self):
        text = self.html.read_text(encoding='utf-8')
        start = text.index('id="accessibility-page"')
        end = text.index('</article>', start)
        broken = text[:end] + text[end + len('</article>'):]
        self.html.write_text(broken, encoding='utf-8')
        guard_before = self.guard.read_bytes()
        code, err = self.run_script()
        self.assertEqual(code, 1)
        self.assertTrue(err)
        self.assertEqual(self.html.read_text(encoding='utf-8'), broken)
        self.assertEqual(self.guard.read_bytes(), guard_before)

    def test_failed_second_write_restores_the_first_file(self):
        from unittest import mock
        from scripts import update_statement_date
        original = self.html.read_bytes()
        real, calls = update_statement_date.write_atomic, []

        def flaky(path, data):
            calls.append(path)
            if len(calls) == 2:
                raise OSError('disk full')
            return real(path, data)

        with mock.patch.object(update_statement_date, 'write_atomic', side_effect=flaky):
            code, err = self.run_script()
        self.assertEqual(code, 1)
        self.assertIn('restored', err)
        self.assertEqual(self.html.read_bytes(), original)


import json
from datetime import datetime
import xml.etree.ElementTree as ET
import shutil
import subprocess
import tempfile
import unittest
import xml.dom.minidom
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
WRITER = ROOT / "assets/statso-xlsx.js"
NODE = shutil.which("node")

DRIVER = """
global.window = {};
require(process.argv[2]);
const X = global.window.Statso.xlsx, S = X.STYLE;
const sheets = [
  {name: 'גיליון ראשון', freezeRows: 3, autoFilter: 'A3:B5', columns: [{width: 18}, {width: 12}], rows: [
    [{v: 'כותרת עם "מרכאות" & <תו>', s: S.title}],
    [],
    [{v: 'חודש', s: S.header}, {v: 'סכום', s: S.header}],
    [{v: '01/2025', s: S.boxed}, {v: 5137.42, s: S.money}],
    [{v: 'סה"כ', s: S.header}, {v: 5137.42, s: S.moneyBold}]
  ]},
  {name: 'שני', rows: [[{v: 'א', s: S.header}, 'ב']]}
 ];
const options = {title: 'כותרת החוברת', created: '2026-10-10T08:00:00Z'};
const write = (suffix, meta) => require('fs').writeFileSync(process.argv[3] + suffix, Buffer.from(X.build(sheets, meta)));
write('', options); write('.again', options); write('.now', {title: options.title});
window.Statso.i18n = {t: s => s, locale: () => 'en-GB'};
write('.en', options);
"""

EXPECTED_PARTS = {"docProps/core.xml", "[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
                  "xl/_rels/workbook.xml.rels", "xl/styles.xml",
                  "xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"}


class XlsxSourceTests(unittest.TestCase):
    def test_site_scripts_have_no_merge_support(self):
        scripts = sorted((ROOT / 'assets').glob('statso-*.js'))
        self.assertTrue(scripts)
        for path in scripts:
            with self.subTest(file=path.name):
                source = path.read_text(encoding='utf-8')
                self.assertNotIn('merges', source)
                self.assertNotIn('mergeCell', source)


@unittest.skipIf(NODE is None, "node is not installed")
class XlsxWriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        driver = Path(cls.temp.name) / "driver.js"
        driver.write_text(DRIVER, encoding="utf-8")
        cls.path = Path(cls.temp.name) / "out.xlsx"
        subprocess.run([NODE, str(driver), str(WRITER), str(cls.path)],
                       check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_archive_is_a_readable_zip_with_every_part(self):
        with zipfile.ZipFile(self.path) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), EXPECTED_PARTS)

    def test_every_part_is_well_formed_xml(self):
        with zipfile.ZipFile(self.path) as archive:
            for name in archive.namelist():
                xml.dom.minidom.parseString(archive.read(name))

    def test_sheets_are_right_to_left_and_carry_the_declared_widths(self):
        with zipfile.ZipFile(self.path) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn('rightToLeft="1"', sheet)
        self.assertIn('width="18"', sheet)

    def test_every_sheet_has_no_merged_cells(self):
        with zipfile.ZipFile(self.path) as archive:
            for name in archive.namelist():
                if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                    with self.subTest(part=name):
                        self.assertNotIn('mergeCell', archive.read(name).decode('utf-8'))
        try:
            import openpyxl   # optional: CI installs no dependencies, the raw-XML check above always runs
        except ImportError:
            return
        book = openpyxl.load_workbook(self.path)
        try:
            for sheet in book.worksheets:
                with self.subTest(sheet=sheet.title):
                    self.assertFalse(sheet.merged_cells.ranges)
        finally:
            book.close()

    def test_special_characters_survive_as_escaped_xml(self):
        with zipfile.ZipFile(self.path) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("&quot;מרכאות&quot;", sheet)
        self.assertIn("&amp;", sheet)
        self.assertIn("&lt;תו&gt;", sheet)
        self.assertNotIn("<תו>", sheet)

    def test_numbers_stay_numeric_and_text_stays_inline(self):
        with zipfile.ZipFile(self.path) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("<v>5137.42</v>", sheet)
        self.assertIn('t="inlineStr"', sheet)

    def test_core_properties_and_package_relationships(self):
        with zipfile.ZipFile(self.path) as archive:
            core = ET.fromstring(archive.read('docProps/core.xml'))
            types = archive.read('[Content_Types].xml').decode()
            rels = archive.read('_rels/.rels').decode()
        dc = '{http://purl.org/dc/elements/1.1/}'
        cp = '{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}'
        dt = '{http://purl.org/dc/terms/}'
        self.assertEqual(core.find(dc + 'title').text, 'כותרת החוברת')
        self.assertEqual(core.find(dc + 'creator').text, 'statso')
        self.assertEqual(core.find(cp + 'lastModifiedBy').text, 'statso')
        self.assertEqual(core.find(dc + 'language').text, 'he-IL')
        for tag in ('created', 'modified'):
            node = core.find(dt + tag)
            self.assertEqual(node.text, '2026-10-10T08:00:00Z')
            self.assertEqual(node.attrib['{http://www.w3.org/2001/XMLSchema-instance}type'], 'dcterms:W3CDTF')
        self.assertIn('<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>', types)
        self.assertIn('<Relationship Id="rId2" Target="docProps/core.xml" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"/>', rels)

    def test_fixed_created_is_byte_identical(self):
        self.assertEqual(self.path.read_bytes(), Path(str(self.path) + '.again').read_bytes())

    def test_current_timestamp_and_language_fallback(self):
        with zipfile.ZipFile(str(self.path) + '.now') as archive:
            core = ET.fromstring(archive.read('docProps/core.xml'))
            created = core.find('{http://purl.org/dc/terms/}created').text
            self.assertRegex(created, r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        with zipfile.ZipFile(str(self.path) + '.en') as archive:
            core = ET.fromstring(archive.read('docProps/core.xml'))
            self.assertEqual(core.find('{http://purl.org/dc/elements/1.1/}language').text, 'en-GB')

    def test_freeze_filter_and_defined_name_only_on_requested_sheet(self):
        with zipfile.ZipFile(self.path) as archive:
            sheet = archive.read('xl/worksheets/sheet1.xml').decode()
            other = archive.read('xl/worksheets/sheet2.xml').decode()
            workbook = archive.read('xl/workbook.xml').decode()
        pane = '<pane ySplit="3" topLeftCell="A4" activePane="bottomLeft" state="frozen"/>'
        self.assertEqual(sheet.count(pane), 1)
        self.assertIn('<selection pane="bottomLeft" activeCell="A4" sqref="A4"/>', sheet)
        self.assertLess(sheet.index('</sheetData>'), sheet.index('<autoFilter ref="A3:B5"/>'))
        self.assertLess(sheet.index('<autoFilter ref="A3:B5"/>'), sheet.index('</worksheet>'))
        self.assertNotIn('<pane', other)
        self.assertNotIn('<autoFilter', other)
        self.assertIn('<definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">&apos;גיליון ראשון&apos;!$A$3:$B$5</definedName>', workbook)
        self.assertEqual(workbook.count('<definedName '), 1)

    def test_a_spreadsheet_library_can_open_it(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl is not installed")
        book = openpyxl.load_workbook(self.path)
        self.assertEqual(book.properties.title, 'כותרת החוברת')
        self.assertEqual(book.properties.creator, 'statso')
        self.assertEqual(book.properties.language, 'he-IL')
        self.assertEqual(book.properties.created, datetime(2026, 10, 10, 8, 0))
        self.assertEqual(book['גיליון ראשון'].freeze_panes, 'A4')
        self.assertEqual(book['גיליון ראשון'].auto_filter.ref, 'A3:B5')
        self.assertIsNone(book['שני'].freeze_panes)
        self.assertIsNone(book['שני'].auto_filter.ref)
        self.assertEqual(book.sheetnames, ["גיליון ראשון", "שני"])
        sheet = book["גיליון ראשון"]
        self.assertTrue(sheet.sheet_view.rightToLeft)
        self.assertEqual(sheet["A4"].value, "01/2025")
        self.assertEqual(sheet["B4"].value, 5137.42)
        self.assertEqual(sheet["B4"].number_format, "#,##0.00")
        self.assertTrue(sheet["A3"].font.b)
        self.assertEqual(sheet.column_dimensions["A"].width, 18)


if __name__ == "__main__":
    unittest.main()

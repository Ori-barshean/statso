import json
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
const bytes = X.build([
  {name: 'גיליון ראשון', columns: [{width: 18}, {width: 12}], merges: ['A1:B1'], rows: [
    [{v: 'כותרת עם "מרכאות" & <תו>', s: S.title}],
    [],
    [{v: 'חודש', s: S.header}, {v: 'סכום', s: S.header}],
    [{v: '01/2025', s: S.boxed}, {v: 5137.42, s: S.money}],
    [{v: 'סה"כ', s: S.header}, {v: 5137.42, s: S.moneyBold}]
  ]},
  {name: 'שני', rows: [[{v: 'א', s: S.header}, 'ב']]}
]);
require('fs').writeFileSync(process.argv[3], Buffer.from(bytes));
"""

EXPECTED_PARTS = {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
                  "xl/_rels/workbook.xml.rels", "xl/styles.xml",
                  "xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"}


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
        self.assertIn('<mergeCell ref="A1:B1"/>', sheet)

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

    def test_a_spreadsheet_library_can_open_it(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl is not installed")
        book = openpyxl.load_workbook(self.path)
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

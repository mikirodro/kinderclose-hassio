import unittest
from custom_components.kinderclose.client import parse_record


def fixture(naps="", stools="", food=""):
    return f'''<h1>Alumno - 2026-10-07</h1>
    <div class="panel"><h3 class="panel-title">Presencia</h3>
    <p><strong>Ausente</strong>: No</p><p><strong>Hora entrada</strong>: --</p></div>
    <div class="panel"><h3 class="panel-title">Comidas</h3>
    <p><strong>Desayuno</strong>: {food}</p></div>
    <div class="panel"><h3 class="panel-title">Dormir</h3><table><tbody>{naps}</tbody></table></div>
    <div class="panel"><h3 class="panel-title">Deposición</h3><table><tbody>{stools}</tbody></table></div>'''


class ParserTests(unittest.TestCase):
    def test_empty_fields_and_no_stools(self):
        record = parse_record(fixture(stools='<tr><td colspan="3">No se encontraron detalles</td></tr>'), "https://example.com")
        self.assertIsNone(record["presencia"]["hora_entrada"])
        self.assertIsNone(record["comidas"]["desayuno"])
        self.assertEqual(record["deposiciones"], [])
        self.assertIsNone(record["sueno_minutos"])

    def test_multiple_naps_and_stools(self):
        record = parse_record(fixture(naps='<tr><td>12:17</td><td>12:40</td></tr><tr><td>14:00</td><td>14:10</td></tr>', stools='<tr><td>Deposición</td><td></td><td></td></tr>'), "https://example.com")
        self.assertEqual(record["sueno_minutos"], 33)
        self.assertEqual(len(record["deposiciones"]), 1)
        self.assertIsNone(record["deposiciones"][0]["hora"])

    def test_incomplete_nap_is_unknown_in_home_assistant(self):
        record = parse_record(fixture(naps='<tr><td>12:11</td><td></td></tr>'), "https://example.com")
        self.assertIsNone(record["sueno_minutos"])

    def test_login_or_changed_page_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_record('<form><input name="password"></form>', "https://example.com")



if __name__ == "__main__":
    unittest.main()

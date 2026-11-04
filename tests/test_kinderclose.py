import unittest
from custom_components.kinderclose.client import ParseError, parse_record


def fixture(naps="", stools="", food="", heading="Alumno - 2026-10-07", extra=""):
    return f'''<h1>{heading}</h1>{extra}
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
        with self.assertRaises(ParseError):
            parse_record('<form><input name="password"></form>', "https://example.com")


class DateTests(unittest.TestCase):
    BIRTH = "<p>Fecha de nacimiento: 01/02/2024</p>"

    def date_of(self, **kwargs):
        return parse_record(fixture(**kwargs), "https://example.com")["fecha"]

    def test_calendar_default_date_has_priority(self):
        script = "<script>$('#cal').datepicker({defaultDate: '2026-10-08'});</script>"
        self.assertEqual(self.date_of(extra=script), "2026-10-08")

    def test_heading_date_wins_over_other_dates_in_the_page(self):
        self.assertEqual(self.date_of(extra=self.BIRTH), "2026-10-07")

    def test_spanish_date_format_is_understood(self):
        self.assertEqual(self.date_of(heading="Ficha del 7/10/2026"), "2026-10-07")

    def test_single_date_in_body_is_used_without_heading_date(self):
        self.assertEqual(self.date_of(heading="Ficha", extra="<p>Día 2026-10-07</p>"), "2026-10-07")

    def test_ambiguous_dates_are_rejected_instead_of_guessed(self):
        with self.assertRaisesRegex(ParseError, "ambigüedad"):
            self.date_of(heading="Ficha", extra="<p>Día 2026-10-07</p>" + self.BIRTH)

    def test_invalid_dates_are_ignored(self):
        self.assertEqual(self.date_of(heading="Ficha 2026-10-07", extra="<p>Ref 2026-13-45</p>"), "2026-10-07")



if __name__ == "__main__":
    unittest.main()

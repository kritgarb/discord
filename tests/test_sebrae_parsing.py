"""Extração dos campos das missões, com textos reais das notícias e editais do Sebrae/SE."""

import unittest
from datetime import date

from feeds.integrations.sebrae import parsing

NEON_INTRO = (
    "O Sebrae Sergipe está com inscrições abertas para uma missão empresarial que levará empreendedores "
    "sergipanos ao Nordeste On 2026 – NEON 2026, o maior encontro de inovação, empreendedorismo e negócios "
    "do Nordeste, que acontecerá na cidade de Maceió (AL), no período de 11 a 13 de junho de 2026."
)
FIPAN_INTRO = (
    "O Sebrae Sergipe está com inscrições abertas para uma missão empresarial que levará empreendedores para "
    "a Feira Internacional de Panificação e Confeitaria – FIPAN 2026 , evento de grande importância para o "
    "segmento de panificação que acontecerá na cidade de São Paulo/SP, no período de 21 a 24 de julho de 2026."
)
WSR_INTRO = (
    "O Sebrae Sergipe está com inscrições abertas para uma missão empresarial que levará empreendedores "
    "sergipanos à Web Summit Rio 26, edição brasileira do maior evento de tecnologia do mundo, que acontecerá "
    "de 08 a 11 de junho de 2026, na cidade do Rio de Janeiro (RJ)."
)


PORTAL_INTRO = (
    "O Sebrae Sergipe está com inscrições abertas para a participação de empreendedores na Missão realizada "
    "pelo Sebrae/SE destinada ao REC'n PLAY 2026 , maior festival gratuito de inovação, tecnologia, criatividade "
    "e cultura do Brasil, que acontecerá na cidade de Recife (PE), no período de 11 a 14 de novembro de 2026."
)
OMNI_INTRO = (
    "O Sebrae Sergipe está com inscrições abertas para uma missão empresarial destinada à participação no "
    "OMNIVAREJO 2026, 58ª Convenção Nacional do Comércio Lojista que acontecerá na cidade de João Pessoa/PB, "
    "no período de 27 a 29 de agosto de 2026."
)


class EventTest(unittest.TestCase):
    def test_event_name_portal_format(self):
        self.assertEqual(parsing.extract_event(PORTAL_INTRO), "REC'n PLAY 2026")
        self.assertEqual(parsing.extract_event(OMNI_INTRO), "OMNIVAREJO 2026")
        self.assertEqual(parsing.extract_location(PORTAL_INTRO), "Recife/PE")

    def test_title_key_matches_across_sources(self):
        self.assertEqual(
            parsing.title_key("Participe da missão do Sebrae/SE para a Deep Tech Summit 2026"),
            parsing.title_key("Participe da Missão do Sebrae/SE  para a DEEP TECH Summit 2026"),
        )

    def test_event_name(self):
        self.assertEqual(parsing.extract_event(NEON_INTRO), "Nordeste On 2026 – NEON 2026")
        self.assertEqual(parsing.extract_event(WSR_INTRO), "Web Summit Rio 26")

    def test_event_name_without_comma_before_que_acontecera(self):
        self.assertEqual(parsing.extract_event(FIPAN_INTRO),
                         "Feira Internacional de Panificação e Confeitaria – FIPAN 2026")

    def test_location_normalizes_uf(self):
        self.assertEqual(parsing.extract_location(NEON_INTRO), "Maceió/AL")
        self.assertEqual(parsing.extract_location(FIPAN_INTRO), "São Paulo/SP")
        self.assertEqual(parsing.extract_location(WSR_INTRO), "Rio de Janeiro/RJ")

    def test_event_dates(self):
        self.assertEqual(parsing.extract_event_dates(NEON_INTRO), "11 a 13 de junho de 2026")
        self.assertEqual(parsing.extract_event_dates(WSR_INTRO), "08 a 11 de junho de 2026")


class DeadlineTest(unittest.TestCase):
    def test_parse_mixed_formats(self):
        self.assertEqual(parsing.parse_dates("de 30/04/2026 a 13 de maio de 2026"),
                         [date(2026, 4, 30), date(2026, 5, 13)])

    def test_period_with_spaces_inside_date(self):
        # texto real extraído do PDF da errata
        self.assertEqual(parsing.deadline_candidates("O período para inscrição será de 17 a 22/ 07/2026, podendo"),
                         [date(2026, 7, 22)])

    def test_latest_extension_wins(self):
        body = ("ficará disponível de 05 a 17/05/2026, podendo ser prorrogado. "
                "O prazo das inscrições foi prorrogado até 02 de junho de 2026. "
                "O prazo das inscrições foi prorrogado até 30 de junho de 2026.")
        self.assertEqual(max(parsing.deadline_candidates(body)), date(2026, 6, 30))


class EditalTest(unittest.TestCase):
    def test_price_with_footnote_and_split_currency(self):
        self.assertEqual(parsing.extract_price(
            "10.1. O valor a ser pago pelo participante nesta Missão será de aproximadamente1 R$ 600,00 (seiscentos"),
            "R$ 600,00")
        self.assertEqual(parsing.extract_price(
            "10.1. O valor a ser pago pelo participante nesta Missão será de aproximadamente R $ 2.750,00 (dois"),
            "R$ 2.750,00")

    def test_last_edital_link_ignoring_results(self):
        html = (
            '<a href="http://x/Edital-Original.pdf">Baixe o edital</a>'
            '<a href="http://x/02.-Resultado.pdf">Resultado da Missão</a>'
            '<a href="http://x/Edital-ALTERADO.pdf">Errata – Edital 17/2026</a>'
            '<a href="http://x/Resultado-final.pdf">Resultado da Missão</a>'
        )
        self.assertEqual(parsing.find_edital_url(html), "https://x/Edital-ALTERADO.pdf")

    def test_signup_url(self):
        self.assertEqual(parsing.find_signup_url('<a href="https://forms.office.com/r/abc">CLIQUE AQUI</a>'),
                         "https://forms.office.com/r/abc")


if __name__ == "__main__":
    unittest.main()

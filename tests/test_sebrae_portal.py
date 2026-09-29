"""Leitura das páginas de missão do Portal Sebrae (.model.json do Adobe AEM)."""

import unittest

from feeds.integrations.sebrae import parsing
from feeds.integrations.sebrae.models import PORTAL
from feeds.integrations.sebrae.source import SebraePortal, parse_portal_model

URL = "https://sebrae.com.br/se/subsites/servicos/missao-recnplay26"
MODEL = {
    "title": "Participe da missão do Sebrae/SE para o REC&#8217;N&#8217;PLAY 2026",
    "description": "Baixe o edital e inscreva-se até 28 de outubro de 2026.&nbsp;",
    "lastModifiedDate": 1790651106023,
    ":items": {"root": {":items": {"responsivegrid": {":items": {
        "teaser": {
            "title": "Participe da missão",
            "actions": [{"url": "/content/dam/se/pdfs/Edital Rec_N_Play 2026_SE.pdf",
                         "title": "Clique aqui e inscreva-se"}],
        },
        "container": {
            "columnClassNames": {"text": "aem-GridColumn aem-GridColumn--default--12 aem-GridColumn--x"},
            ":items": {
                "text": {"text": "<p>O Sebrae Sergipe está com inscrições abertas ... destinada ao REC'n PLAY 2026 , "
                                 "maior festival, que acontecerá na cidade de Recife (PE), no período de "
                                 "11 a 14 de novembro de 2026.</p><p>Inscreva-se "
                                 '<a href="https://forms.cloud.microsoft/r/abc">aqui</a>.</p>'},
                "buttongroup": {":items": {"button0": {
                    "text": "Baixe o edital para a Missão REC'n Play 2026",
                    "link": "/content/dam/se/pdfs/Edital%20Rec_N_Play%202026_SE.pdf",
                }}},
            },
        },
    }}}}},
}


class PortalModelTest(unittest.TestCase):
    def setUp(self):
        self.mission = parse_portal_model(MODEL, URL)

    def test_basic_fields(self):
        m = self.mission
        self.assertEqual(m.source, PORTAL)
        self.assertEqual(m.guid, URL)
        self.assertEqual(m.title, "Participe da missão do Sebrae/SE para o REC’N’PLAY 2026")
        self.assertEqual(m.published.year, 2026)

    def test_text_ignores_css_classes(self):
        intro = parsing.first_paragraph(self.mission.content_html)
        self.assertTrue(intro.startswith("O Sebrae Sergipe"))
        self.assertEqual(parsing.extract_event(intro), "REC'n PLAY 2026")

    def test_links_become_absolute_and_encoded(self):
        edital = parsing.find_edital_url(self.mission.content_html)
        self.assertEqual(edital, "https://sebrae.com.br/content/dam/se/pdfs/Edital%20Rec_N_Play%202026_SE.pdf")
        self.assertEqual(parsing.find_signup_url(self.mission.content_html), "https://forms.cloud.microsoft/r/abc")

    def test_deadline_from_description(self):
        self.assertIn(parsing.parse_dates("28 de outubro de 2026")[0],
                      parsing.deadline_candidates(self.mission.description))


class PortalUrlFilterTest(unittest.TestCase):
    def test_only_se_subsite_missions(self):
        match = SebraePortal.MISSION_URL_RE.match
        self.assertTrue(match("https://sebrae.com.br/se/subsites/servicos/missao-recnplay26"))
        self.assertTrue(match("https://sebrae.com.br/se/subsites/servicos/missao_fenalaw26"))
        self.assertFalse(match("https://sebrae.com.br/se/sobre-nos/missoes-tecnicas-2026"))   # página de listagem
        self.assertFalse(match("https://sebrae.com.br/ba/subsites/missao-rio2c-2026"))         # outro estado


if __name__ == "__main__":
    unittest.main()

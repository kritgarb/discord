# 002. Missões Sebrae/SE: Especificação

| | |
|---|---|
| **Status** | Implementada |
| **Plano** | [plan.md](plan.md) |
| **Depende de** | [001. Plataforma de feeds](../001-plataforma-feeds/spec.md) |

## Contexto

O Sebrae/SE abre **missões empresariais**: viagens subsidiadas para feiras e eventos, com edital, vagas limitadas e prazo curto de inscrição. Hoje elas são divulgadas em dois lugares e sem aviso ativo:

- **Agência Sebrae de Notícias (SE)**: notícias, com RSS.
- **Portal Sebrae** (`sebrae.com.br/se/subsites/…`): páginas próprias, sem RSS. Em setembro/2026, 8 das 9 missões estavam **só** aqui.

As informações que importam (valor, prazo) costumam estar só no **edital em PDF**. Quem quer participar precisa saber cedo, e com o essencial em mãos.

## Histórias de usuário

- **Como** empreendedor no canal, **quero** ser avisado de cada missão com inscrições abertas, **para** não perder o prazo.
- **Como** empreendedor, **quero** ver evento, local, data, valor e prazo direto na mensagem, **para** decidir sem abrir o edital.
- **Como** membro do canal, **não quero** receber missões já encerradas nem a mesma missão duas vezes.

## Requisitos

| ID | Requisito | Verificação |
|---|---|---|
| MIS-01 | O sistema DEVE buscar missões no feed RSS principal da Agência (`se.agenciasebrae.com.br/feed/`): 3 páginas por execução, e até 30 na primeira execução ou no `--test`. | manual |
| MIS-02 | O sistema DEVE buscar missões no Portal Sebrae, considerando só páginas do sitemap em `sebrae.com.br/se/subsites/` cuja URL contenha "miss". | automatizada |
| MIS-03 | QUANDO uma página do Portal já estiver no estado, o sistema NÃO DEVE baixá-la de novo numa execução normal. | manual (revisão de código) |
| MIS-04 | O sistema DEVE considerar como missão apenas itens cujo título contenha "missão" ou "missões" (com ou sem acento). | manual |
| MIS-05 | QUANDO a mesma missão aparecer nas duas fontes, o sistema DEVE tratá-la como um item só, comparando o título normalizado (sem acento, pontuação ou diferença de caixa). | automatizada |
| MIS-06 | O sistema DEVE publicar, para cada missão, um card com os campos: Evento, Local, Data, Valor (participante) e Inscrições até, mais links para a página, o edital e o formulário de inscrição. Campos não encontrados DEVEM ser omitidos. | manual |
| MIS-07 | SE menos de 2 campos forem extraídos, ENTÃO o card DEVE mostrar o resumo da página. | manual |
| MIS-08 | O sistema DEVE extrair o nome do evento do primeiro parágrafo, nos padrões da Agência ("levará empreendedores ao X, …") e do Portal ("Missão … destinada ao X, …"). | automatizada |
| MIS-09 | O sistema DEVE extrair o local no formato `Cidade/UF` e o período do evento a partir do texto, usando o preâmbulo do edital como alternativa. | automatizada |
| MIS-10 | O sistema DEVE extrair o valor pago pelo participante do edital (item 10.1, "O valor a ser pago pelo participante… R$ X"). | automatizada |
| MIS-11 | O sistema DEVE considerar como prazo de inscrição a **data mais recente** entre: período de inscrição do texto, descrição ("inscreva-se até…"), prorrogações ("prorrogado até…") e item 8.3 do edital mais recente. | automatizada |
| MIS-12 | O sistema DEVE usar como edital o **último** link de PDF com "edital" no conteúdo, ignorando resultados, com URL absoluta e codificada. | automatizada |
| MIS-13 | O sistema DEVE identificar o link do formulário de inscrição (`forms.office.com`, `forms.cloud.microsoft`). | automatizada |
| MIS-14 | QUANDO o prazo de inscrição for anterior a hoje (Brasília), o sistema NÃO DEVE publicar a missão e DEVE marcá-la como vista. Missões sem prazo identificado DEVEM ser publicadas. | manual |
| MIS-15 | SE o edital não puder ser baixado ou lido, ENTÃO o sistema DEVE publicar a missão sem o valor e registrar um aviso no log. | manual |
| MIS-16 | SE uma página do Portal não puder ser lida, ENTÃO o sistema DEVE registrar um aviso e continuar com as demais. | manual |
| MIS-17 | No texto do Portal, o sistema DEVE ignorar campos que não são conteúdo, como classes CSS de layout. | automatizada |

### Critérios de aceite

- **MIS-05**: "Participe da missão do Sebrae/SE para a Deep Tech Summit 2026" (Agência) e "Participe da Missão do Sebrae/SE  para a DEEP TECH Summit 2026" (Portal) geram a mesma chave, e a missão é publicada uma vez.
- **MIS-11**: um texto com período "05 a 17/05/2026", depois "prorrogado até 02 de junho de 2026" e "prorrogado até 30 de junho de 2026" resulta em prazo **30/06/2026**. Uma errata cujo item 8.3 diga "17 a 22/ 07/2026" (espaço dentro da data, como no PDF real) resulta em **22/07/2026**.
- **MIS-14**: em 29/09/2026, a missão Febratex (prazo 22/07) é ignorada, e a REC'N'PLAY (prazo 28/10) é publicada.

### Verificação manual

- `python -m feeds missoes --test 3 --dry-run`: mostra os campos extraídos das 3 missões mais recentes.
- `python -m feeds missoes --dry-run`: mostra "Ignorado (inscrições encerradas em …)" para as encerradas e os campos das abertas.

## Fora de escopo

- Missões de outros estados.
- Avisar de novo quando uma missão já publicada tiver o prazo prorrogado (ver questões em aberto).
- Corrigir erros do próprio site: o card reproduz o que está publicado (ex.: "São Paulo (PE)" na Fenalaw 2026).
- Garantir o valor final: o edital informa um valor **aproximado**.

## Questões em aberto

- [ ] Republicar quando uma missão tiver o prazo prorrogado? Hoje ela fica marcada como vista (plano 001, D4).
- [ ] Mencionar um cargo (ex.: `@Missões`) nas publicações? Hoje FEED-10 proíbe menções.
- [ ] Criar um teste automatizado para `SebraeMissoes.skip_reason` e para a montagem do card (MIS-06/07/14).

## Rastreabilidade

| Requisito | Código | Teste |
|---|---|---|
| MIS-01 | `feeds/integrations/sebrae/source.py` → `SebraeFeed`; `integration.py` → `SebraeMissoes._from_agencia` | manual |
| MIS-02 | `source.py` → `SebraePortal.mission_urls`, `MISSION_URL_RE`; `parse_portal_model` | `tests/test_sebrae_portal.py::PortalUrlFilterTest.test_only_se_subsite_missions`, `::PortalModelTest.test_basic_fields` |
| MIS-03 | `SebraeMissoes._from_portal` | manual |
| MIS-04 | `SebraeMissoes.MISSION_RE` | manual |
| MIS-05 | `parsing.title_key`; `SebraeMissoes.fetch`, `SebraeMissoes.keys` | `tests/test_sebrae_parsing.py::EventTest.test_title_key_matches_across_sources` |
| MIS-06 | `SebraeMissoes.fields`, `SebraeMissoes.to_embed` | manual |
| MIS-07 | `SebraeMissoes.to_embed` | manual |
| MIS-08 | `parsing.extract_event`, `EVENT_RE` | `::EventTest.test_event_name`, `::test_event_name_without_comma_before_que_acontecera`, `::test_event_name_portal_format`; `tests/test_sebrae_portal.py::PortalModelTest.test_text_ignores_css_classes` |
| MIS-09 | `parsing.extract_location`, `parsing.extract_event_dates`; `MissionExtractor.extract` | `::EventTest.test_location_normalizes_uf`, `::test_event_dates` |
| MIS-10 | `parsing.extract_price` | `::EditalTest.test_price_with_footnote_and_split_currency` |
| MIS-11 | `parsing.deadline_candidates`, `parsing.parse_dates`; `MissionExtractor.extract` | `::DeadlineTest.test_parse_mixed_formats`, `::test_period_with_spaces_inside_date`, `::test_latest_extension_wins`; `tests/test_sebrae_portal.py::PortalModelTest.test_deadline_from_description` |
| MIS-12 | `parsing.find_edital_url`; `parse_portal_model` (`absolute`) | `::EditalTest.test_last_edital_link_ignoring_results`; `tests/test_sebrae_portal.py::PortalModelTest.test_links_become_absolute_and_encoded` |
| MIS-13 | `parsing.find_signup_url` | `::EditalTest.test_signup_url`; `PortalModelTest.test_links_become_absolute_and_encoded` |
| MIS-14 | `SebraeMissoes.skip_reason` (+ FEED-04) | manual; fluxo genérico em `tests/test_integration.py::IntegrationFlowTest.test_skipped_items_are_not_posted_but_marked_as_seen` |
| MIS-15 | `MissionExtractor.extract` | manual |
| MIS-16 | `SebraeMissoes._from_portal` | manual |
| MIS-17 | `parse_portal_model` (só textos com HTML) | `tests/test_sebrae_portal.py::PortalModelTest.test_text_ignores_css_classes` |

## Histórico

| Data | Mudança |
|---|---|
| 2026-09-29 | Implementação inicial com a busca da Agência (`?s=missão`) |
| 2026-09-29 | Troca para o feed principal: o índice da busca estava desatualizado e perdia missões |
| 2026-09-29 | Extração de campos da página e do edital (MIS-06 a MIS-13); o RSS trazia conteúdo desatualizado |
| 2026-09-29 | Portal Sebrae como fonte (MIS-02, MIS-03, MIS-05, MIS-16, MIS-17) e regra de inscrições encerradas (MIS-14), depois de a missão REC'N'PLAY não ser detectada |
| 2026-09-30 | Spec retroativa escrita na adoção do SDD |

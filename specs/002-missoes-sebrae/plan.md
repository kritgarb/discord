# 002. Missões Sebrae/SE: Plano técnico

| | |
|---|---|
| **Spec** | [spec.md](spec.md) |

## Visão geral

`SebraeMissoes` é uma `Integration` (spec 001) que junta duas fontes, deduplica pelo título, extrai os campos da página e do edital e descarta as missões encerradas.

```
Agência: feed RSS (paginado) ─┐
                              ├─► filtro "missão" ─► agrupa por title_key ─► novos? ─► MissionExtractor ─► encerrada? ─► card
Portal: sitemap ─► .model.json┘                                                       (página + edital PDF)
```

## Componentes

| Componente | Responsabilidade | Arquivo |
|---|---|---|
| `SebraeMissoes` | Integração: combina as fontes, chaves, `skip_reason`, montagem do card | `feeds/integrations/sebrae/integration.py` |
| `SebraeFeed` | Lê uma página do RSS principal da Agência | `feeds/integrations/sebrae/source.py` |
| `SebraePortal` | Lista as URLs de missão do sitemap e lê o `.model.json` de cada página | `source.py` |
| `parse_portal_model` | Converte o JSON do Adobe AEM numa `Mission` (textos HTML + links viram `content_html`) | `source.py` |
| `MissionExtractor` | Busca o corpo atualizado da notícia (só Agência) e o PDF do edital, e preenche os campos | `source.py` |
| `parsing` | Funções puras: datas, prazo, evento, local, valor, edital, formulário, `title_key` | `feeds/integrations/sebrae/parsing.py` |
| `Mission` | Dataclass com os dados brutos, a `source` (Agência/Portal) e os campos extraídos | `feeds/integrations/sebrae/models.py` |

## Modelo de dados

- **`Mission`**: `guid`, `title`, `link`, `description`, `content_html`, `published`, `image`, `source`, mais os campos extraídos: `event`, `location`, `dates`, `price`, `deadline`, `edital_url` e `signup_url`.
- **Chaves no estado**: `{guid, link, "title:<título normalizado>"}`. Na Agência, o `guid` é `?p=ID`; no Portal, `guid = link = URL da página`.
- **Data de publicação no Portal**: `lastModifiedDate` do `.model.json` (o Portal não expõe a data de publicação).

## Decisões

| # | Decisão | Alternativas descartadas | Motivo |
|---|---|---|---|
| D1 | Feed principal paginado da Agência | Busca `?s=missão&feed=rss2` | O índice da busca estava desatualizado e não trazia missões de junho/2026. |
| D2 | Corpo da notícia lido da **página** (`div.text-content`) | `content:encoded` do RSS | O RSS vinha sem as prorrogações e erratas mais recentes. |
| D3 | Portal via `sitemap.xml` + `.model.json` | Raspar o HTML renderizado; API de busca | A página é um app em JS (sem conteúdo no HTML). O AEM expõe o conteúdo estruturado em `.model.json`, e o sitemap lista todas as páginas. |
| D4 | O `content_html` do Portal é sintetizado (textos + `<a>` para botões e ações) | Um extrator separado para o Portal | Reaproveita as mesmas funções de `parsing` para as duas fontes. |
| D5 | Deduplicação entre fontes pelo título normalizado | Pela URL; manter as duas | As URLs das duas fontes são diferentes; o título é o mesmo (a menos de caixa e acentos). |
| D6 | Prazo = a maior data entre todas as fontes de prazo | A primeira encontrada; só o edital | Prorrogações e erratas sempre estendem; a maior data é a vigente. |
| D7 | Descartar missões encerradas (`skip_reason`) | Publicar tudo | Na primeira leitura do Portal, 7 das 9 missões estavam encerradas; publicá-las seria spam (C1). |
| D8 | Ler o PDF com `pypdf` e normalizar espaços | OCR; outras libs | Os editais são PDFs de texto. `pypdf` é pura em Python (C6). Espaços quebrados ("R $", "22/ 07") são tratados nas regex. |

## Verificação da constituição

| Princípio | Como é atendido |
|---|---|
| C1 Não fazer spam | Chaves múltiplas + `title_key` (MIS-05); encerradas descartadas (MIS-14); páginas vistas do Portal não são reprocessadas (MIS-03) |
| C2 Não postar errado | Campos não encontrados são omitidos; nada é inferido além do texto publicado |
| C3 Testável sem rede | `parsing` é puro; `parse_portal_model` recebe um dict; testes com textos reais |
| C4 Segredos | `DISCORD_WEBHOOK_URL` |
| C5 Horário de Brasília | `skip_reason` usa `clock.today()` |
| C6 Dependências | Só `pypdf` além da biblioteca padrão |
| C7 Privacidade | Sem menções (FEED-10) |

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Sebrae muda o texto padrão das páginas ou dos editais | Campos somem do card | Omitir campos em vez de errar (C2); testes com textos reais; `--test N --dry-run` para conferir |
| Portal muda de plataforma ou o `.model.json` some | Missões do Portal deixam de chegar | Falha logada por página (MIS-16); a Agência continua funcionando |
| Prazo prorrogado depois de a missão ser marcada como encerrada | Missão reaberta não é anunciada | Questão em aberto na spec |
| Muitos PDFs novos numa execução | Execução mais lenta | Só itens novos são enriquecidos; páginas vistas não são rebaixadas |

## Estratégia de teste

- **Unitário** (`tests/test_sebrae_parsing.py`, `tests/test_sebrae_portal.py`): extração com trechos reais das notícias, editais e do JSON do Portal, incluindo as armadilhas encontradas (espaços dentro de datas e de "R$", CSS no JSON, links relativos com espaço).
- **Manual**: ver "Verificação manual" na spec.

## Configuração e deploy

- Secret `DISCORD_WEBHOOK_URL` (canal de missões).
- Estado em `state/missoes.json`.

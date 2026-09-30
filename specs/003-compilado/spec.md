# 003. Compilado do Código Fonte TV: Especificação

| | |
|---|---|
| **Status** | Implementada |
| **Plano** | [plan.md](plan.md) |
| **Depende de** | [001. Plataforma de feeds](../001-plataforma-feeds/spec.md) |

## Contexto

O [Compilado do Código Fonte TV](https://compilado.codigofonte.com.br/) publica, mais ou menos toda semana, as principais notícias do mundo da programação. Queremos que cada edição nova apareça num canal próprio, com as manchetes, sem ninguém precisar lembrar de conferir o site.

O site não tem RSS, o conteúdo completo é exclusivo para inscritos, e as edições não saem num dia fixo (às vezes várias no mesmo dia).

## Histórias de usuário

- **Como** membro do canal, **quero** ver as manchetes da edição nova assim que ela sair, **para** decidir se vou ler ou assistir.
- **Como** dono do canal, **não quero** que o histórico inteiro seja despejado quando a integração for ativada.

## Requisitos

| ID | Requisito | Verificação |
|---|---|---|
| CMP-01 | O sistema DEVE obter as edições publicadas a partir da home do site, ignorando as que não têm data de publicação, e ordená-las da mais antiga para a mais nova. | automatizada |
| CMP-02 | O sistema DEVE separar, no título da edição, o nome (antes de " - ") das manchetes (separadas por ";"). | automatizada |
| CMP-03 | SE a home não tiver o formato esperado, ENTÃO o sistema DEVE falhar com uma mensagem clara e NÃO DEVE publicar nada. | automatizada |
| CMP-04 | QUANDO a integração rodar pela primeira vez, o sistema DEVE marcar como vistas as edições publicadas **antes de hoje** (Brasília) e publicar só as de hoje. | automatizada |
| CMP-05 | Depois da primeira execução, o sistema DEVE publicar toda edição ainda não vista, inclusive as publicadas perto da meia-noite e vistas só na execução seguinte. | automatizada (via FEED-02) |
| CMP-06 | O sistema DEVE publicar um card com o nome da edição como título (com link), as manchetes em tópicos, links para a edição, o YouTube e o Spotify, e o banner. | manual |
| CMP-07 | O sistema DEVE identificar cada edição pelo `uid` da plataforma. | manual (revisão de código) |

### Critérios de aceite

- **CMP-02**: `"COMPILADO #263 - Líderes tech divergem sobre frear IA; CEO da Automattic de volta; "` → nome `COMPILADO #263` e manchetes `["Líderes tech divergem sobre frear IA", "CEO da Automattic de volta"]`.
- **CMP-04**: em 29/09/2026, uma edição publicada às 01:00 UTC de 29/09 (22:00 de 28/09 em Brasília) conta como "antes de hoje" e **não** é publicada na primeira execução.

### Verificação manual

- `python -m feeds compilado --test --dry-run`: mostra a edição mais recente com as manchetes.
- `python -m feeds compilado --test`: publica a edição mais recente no canal, para conferir o card.

## Fora de escopo

- O conteúdo completo das edições (exclusivo para inscritos).
- Vídeo ou episódio específico no YouTube/Spotify: os links são dos canais.

## Questões em aberto

- Nenhuma.

## Rastreabilidade

| Requisito | Código | Teste |
|---|---|---|
| CMP-01 | `feeds/integrations/compilado/source.py` → `parse_home`, `CompiladoSite.editions` | `tests/test_compilado.py::ParseTest.test_parse_home_sorts_and_skips_unpublished` |
| CMP-02 | `source.py` → `split_title` | `::ParseTest.test_split_title` |
| CMP-03 | `parse_home` (`RuntimeError`) | `::ParseTest.test_missing_next_data_raises` |
| CMP-04 | `feeds/integrations/compilado/integration.py` → `Compilado.bootstrap` | `::BootstrapTest.test_first_run_skips_editions_before_today_in_brasilia` |
| CMP-05 | `Integration.pending` (spec 001) | `tests/test_integration.py::IntegrationFlowTest.test_bootstrap_marks_items_as_seen_on_first_run_only` |
| CMP-06 | `Compilado.to_embed` | manual |
| CMP-07 | `Compilado.keys` | manual |

## Histórico

| Data | Mudança |
|---|---|
| 2026-09-29 | Implementação inicial |
| 2026-09-30 | Spec retroativa escrita na adoção do SDD |

# 001. Plataforma de feeds: Especificação

| | |
|---|---|
| **Status** | Implementada |
| **Plano** | [plan.md](plan.md) |

## Contexto

Queremos publicar em canais do Discord, automaticamente, conteúdo de sites que não têm integração com o Discord (e às vezes nem RSS). Cada fonte vira uma **integração** que roda de hora em hora sem servidor próprio (GitHub Actions) e publica por **webhook** no canal correspondente.

Esta spec define o comportamento **comum a todas as integrações**. O que cada uma busca e como monta a mensagem fica na spec dela (002, 003…).

## Histórias de usuário

- **Como** membro de um canal, **quero** receber cada novidade uma única vez, **para** não ser inundado por mensagens repetidas.
- **Como** dono do projeto, **quero** adicionar uma nova fonte implementando só o que é específico dela, **para** não reescrever o fluxo de publicação.
- **Como** dono do projeto, **quero** testar o formato das mensagens sem mexer no que já foi enviado, **para** ajustar o visual com segurança.

## Requisitos

| ID | Requisito | Verificação |
|---|---|---|
| FEED-01 | O sistema DEVE executar todas as integrações registradas com `python -m feeds all`, e uma integração específica com `python -m feeds <slug>`. | manual |
| FEED-02 | QUANDO um item encontrado tiver **qualquer** uma de suas chaves já registrada no estado da integração, o sistema NÃO DEVE publicá-lo. | automatizada |
| FEED-03 | QUANDO a integração rodar pela primeira vez (sem arquivo de estado), o sistema DEVE marcar como vistos, sem publicar, os itens indicados pela integração (*bootstrap*). Por padrão, nenhum item é marcado e todos são publicados. | automatizada |
| FEED-04 | QUANDO a integração indicar um motivo para não publicar um item novo (*skip reason*), o sistema NÃO DEVE publicá-lo e DEVE marcá-lo como visto, registrando o motivo no log. | automatizada |
| FEED-05 | QUANDO executado com `--dry-run`, o sistema DEVE mostrar no terminal o que seria publicado e NÃO DEVE enviar mensagens nem alterar o estado. | automatizada |
| FEED-06 | QUANDO executado com `--test N`, o sistema DEVE publicar os N itens mais recentes, ignorando o estado e o *skip reason*, e NÃO DEVE alterar o estado. | automatizada |
| FEED-07 | O sistema DEVE salvar o estado ao fim de cada execução normal, inclusive quando nada for publicado ou o envio falhar no meio, preservando o que já foi enviado. | automatizada (parcial) |
| FEED-08 | SE o Discord responder com rate limit (HTTP 429), ENTÃO o sistema DEVE aguardar o tempo indicado e tentar de novo, até 5 vezes. | manual |
| FEED-09 | SE uma integração falhar no `all`, ENTÃO o sistema DEVE executar as demais e terminar com código de saída 1. | manual |
| FEED-10 | As mensagens publicadas NÃO DEVEM mencionar usuários nem cargos. | manual (revisão de código) |
| FEED-11 | SE o webhook de uma integração não estiver configurado, ENTÃO o sistema DEVE falhar com uma mensagem dizendo qual variável definir. | manual |
| FEED-12 | O sistema DEVE rodar de hora em hora no GitHub Actions, executando os testes antes de publicar, e NÃO DEVE publicar se os testes falharem. | manual |
| FEED-13 | QUANDO o estado mudar numa execução do Actions, o sistema DEVE fazer commit e push dele, tentando até 5 vezes (com `pull --rebase` antes de cada tentativa); SE todas falharem, ENTÃO o job DEVE falhar com um aviso de que a próxima execução reenviaria as mensagens. | manual |

### Critérios de aceite

- **FEED-02**: *Dado* um estado contendo `https://site/post`, *quando* aparecer um item com as chaves `{https://site/post, ?p=1}`, *então* ele não é publicado.
- **FEED-03**: *Dado* que não existe `state/<slug>.json` e que o *bootstrap* devolve o item "antigo", *quando* a integração roda com os itens "antigo" e "hoje", *então* só "hoje" é publicado. *Quando* ela roda de novo com um item "novo", *então* o *bootstrap* não se aplica mais e "novo" é publicado.
- **FEED-06**: *Dado* um item já publicado, *quando* rodar `--test 1`, *então* o item é publicado de novo e o arquivo de estado fica byte a byte igual.

### Verificação manual

- **FEED-01/05**: `python -m feeds all --dry-run` lista cada integração com "N encontrados, M novos".
- **FEED-08/10**: revisão de `feeds/core/discord.py` (laço de 429 e `allowed_mentions: {parse: []}`).
- **FEED-09/11**: rodar `python -m feeds all --test 1` sem as variáveis de webhook (o webhook só é exigido quando há algo a enviar). Cada integração loga a variável ausente, e o processo sai com código 1.
- **FEED-12/13**: conferir o log do job em *Actions → Feeds → Discord*.

## Fora de escopo

- Servidor próprio ou execução contínua: as integrações são jobs agendados.
- Edição ou remoção de mensagens já publicadas.
- Estado em banco de dados: o estado é um JSON versionado (ver plano, D1).

## Questões em aberto

- [ ] O GitHub desativa o cron após 60 dias sem atividade no repositório. Vale gerar um commit periódico para mantê-lo ativo?

## Rastreabilidade

| Requisito | Código | Teste |
|---|---|---|
| FEED-01 | `feeds/__main__.py` → `main`; `feeds/integrations/__init__.py` → `INTEGRATIONS` | manual |
| FEED-02 | `feeds/core/integration.py` → `Integration.pending`; `feeds/core/state.py` → `SeenStore.contains_any` | `tests/test_integration.py::IntegrationFlowTest.test_does_not_repost`, `::test_any_matching_key_counts_as_seen` |
| FEED-03 | `Integration.pending`, `Integration.bootstrap` | `::test_first_run_posts_everything_and_saves_state`, `::test_bootstrap_marks_items_as_seen_on_first_run_only` |
| FEED-04 | `Integration.pending`, `Integration.skip_reason` | `::test_skipped_items_are_not_posted_but_marked_as_seen` |
| FEED-05 | `Integration.run` (`dry_run`) | `::test_dry_run_sends_and_saves_nothing` |
| FEED-06 | `Integration.pending` / `run` (`test`) | `::test_test_mode_resends_latest_without_touching_state`, `::test_skip_reason_is_ignored_in_test_mode` |
| FEED-07 | `Integration.run` (`finally: state.save()`) | `::test_state_saved_even_when_everything_is_skipped` (falha no meio do envio: manual) |
| FEED-08 | `feeds/core/discord.py` → `DiscordWebhook.send` | manual |
| FEED-09 | `feeds/__main__.py` → `main` | manual |
| FEED-10 | `DiscordWebhook.send_embed` | manual |
| FEED-11 | `feeds/core/config.py` → `require_env`, `ConfigError` | manual |
| FEED-12 | `.github/workflows/feeds.yml` (cron, passo "Testes") | manual |
| FEED-13 | `.github/workflows/feeds.yml` (passo "Salvar estado") | manual |

## Histórico

| Data | Mudança |
|---|---|
| 2026-09-29 | Implementação inicial (missões) e refatoração para a classe base `Integration` |
| 2026-09-29 | FEED-04 (*skip reason*) adicionado junto com o Portal Sebrae |
| 2026-09-29 | FEED-13: push do estado com novas tentativas, após uma falha transitória do GitHub |
| 2026-09-30 | Spec retroativa escrita na adoção do SDD |

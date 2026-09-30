# 004. Bot de ponto dos freelas: Especificação

| | |
|---|---|
| **Status** | Implementada |
| **Plano** | [plan.md](plan.md) |

## Contexto

Freelas prestam serviço por hora e as horas são combinadas informalmente, o que gera esquecimentos e conferência manual no fim do mês. Queremos um relógio de ponto dentro do Discord, onde o time já conversa: cada freela registra o próprio tempo, e o admin tem o total de cada um para pagar.

Decisões de produto tomadas com o dono (2026-09-29): registro por **relógio de ponto** (entrar/sair), **só horas totais** (sem projetos nem valor/hora), cada freela vê **só as próprias** horas, e hospedagem numa **VPS própria**.

## Histórias de usuário

- **Como** freela, **quero** abrir e fechar meu ponto com um comando, **para** registrar meu tempo sem planilha.
- **Como** freela, **quero** pausar o ponto, **para** que intervalos não contem.
- **Como** freela, **quero** consultar minhas horas do dia, da semana e do mês, **para** acompanhar o que tenho a receber.
- **Como** freela, **quero** que só eu veja meus registros, **para** ter privacidade.
- **Como** admin, **quero** um relatório por pessoa com planilha, **para** fazer o pagamento do mês.
- **Como** admin, **quero** corrigir esquecimentos (ponto aberto, horas fora do Discord), **para** que o total fique certo.
- **Como** freela, **quero** ser lembrado se esquecer o ponto aberto, **para** não inflar minhas horas.

## Requisitos

### Freela

| ID | Requisito | Verificação |
|---|---|---|
| PNT-01 | QUANDO um freela usar `/entrar [nota]`, o sistema DEVE abrir um ponto para ele naquele servidor, com a nota opcional. | automatizada |
| PNT-02 | SE o freela já tiver um ponto aberto naquele servidor, ENTÃO o sistema DEVE recusar o `/entrar` informando desde quando o ponto está aberto. Pessoas e servidores são independentes. | automatizada |
| PNT-03 | QUANDO o freela usar `/pausa`, o sistema DEVE pausar o ponto; QUANDO usar `/retomar`, DEVE retomá-lo. O tempo em pausa NÃO DEVE contar. Pausar um ponto já pausado ou retomar um que não está pausado DEVE ser recusado. | automatizada |
| PNT-04 | QUANDO o freela usar `/sair`, o sistema DEVE fechar o ponto (encerrando também uma pausa em andamento) e informar a duração da sessão e o total do mês. Sem ponto aberto, DEVE recusar. | automatizada |
| PNT-05 | QUANDO o freela usar `/status`, o sistema DEVE informar se o ponto está aberto, pausado ou fechado, o tempo trabalhado até agora e o total do dia. | manual |
| PNT-06 | QUANDO o freela usar `/horas [periodo]`, o sistema DEVE listar as sessões e os ajustes dele no período (padrão: este mês), com o total. | manual |

### Admin

| ID | Requisito | Verificação |
|---|---|---|
| PNT-07 | Os comandos de admin (`/ponto-admin …`) DEVEM ser visíveis e utilizáveis só por quem tem a permissão **Gerenciar servidor** (ou por quem o servidor liberar nas Integrações). | manual |
| PNT-08 | QUANDO o admin usar `/ponto-admin relatorio [periodo] [freela]`, o sistema DEVE mostrar as horas por pessoa, da maior para a menor, com o total geral, e anexar um CSV (separador `;`, UTF-8 com BOM) com uma linha por sessão e por ajuste. | automatizada (ordem); manual (CSV) |
| PNT-09 | QUANDO o admin usar `/ponto-admin ajustar <freela> <duracao> <motivo>`, o sistema DEVE registrar um ajuste positivo ou negativo (`1h30`, `45m`, `-0h15`). Ajuste zero, sem motivo ou com duração inválida DEVE ser recusado. | automatizada |
| PNT-10 | QUANDO o admin usar `/ponto-admin fechar <freela> [HH:MM]`, o sistema DEVE fechar o ponto aberto do freela no horário informado (ou agora). Um horário que ainda não chegou hoje DEVE ser entendido como de ontem. O horário DEVE ficar entre a entrada e agora. | automatizada |
| PNT-11 | QUANDO o admin usar `/ponto-admin abertos`, o sistema DEVE listar quem está com o ponto aberto no servidor. | automatizada (serviço) |

### Regras gerais

| ID | Requisito | Verificação |
|---|---|---|
| PNT-12 | Os totais DEVEM considerar só sessões **encerradas**, atribuídas ao período da **data de entrada**, mais os ajustes pela data em que foram feitos. | automatizada |
| PNT-13 | Os períodos DEVEM ser: hoje, esta semana, semana passada, este mês e mês passado, com semanas começando na segunda-feira, no horário de Brasília. | automatizada |
| PNT-14 | ENQUANTO um ponto estiver aberto (e não pausado) com mais de `PONTO_LEMBRETE_HORAS` de trabalho, o sistema DEVE mandar **uma** DM ao freela lembrando de sair, e só uma por sessão, mesmo se a DM falhar. Com o valor `0`, o lembrete fica desligado. | automatizada (serviço) |
| PNT-15 | As respostas aos comandos DEVEM ser privadas (efêmeras), e os comandos DEVEM funcionar só dentro de servidores, não em DM. | manual |
| PNT-16 | SE houver erro de regra ou de entrada, ENTÃO o sistema DEVE responder em privado com uma mensagem clara; SE houver erro inesperado, ENTÃO DEVE responder com uma mensagem genérica e registrar o erro no log. | manual |
| PNT-17 | SE o bot não tiver acesso ao servidor configurado ou o token for inválido, ENTÃO a inicialização DEVE falhar com uma mensagem dizendo o que conferir (incluindo o link de convite). | manual |
| PNT-18 | Os dados DEVEM persistir entre reinícios e atualizações do bot. | manual |

### Critérios de aceite

- **PNT-03/04**: entra às 09:00, pausa às 10:00, retoma às 10:30, pausa às 11:30 e sai às 11:45 (em pausa) → sessão de **2h 00min**.
- **PNT-10**: ponto aberto às 09:00 e fechado pelo admin às 19:00 com `horario:12:00` → **3h 00min**. Um horário antes da entrada ou no futuro é recusado.
- **PNT-12**: entra em 30/09 às 23:00 e sai em 01/10 às 01:00 → 2h em **setembro**, 0h em outubro.
- **PNT-14**: com limite de 8h, nada aos 7h de trabalho; lembrete aos 9h; nenhum segundo lembrete depois.

### Verificação manual

1. Com o bot no ar, como freela: `/entrar`, `/pausa`, `/retomar`, `/status`, `/sair`, `/horas`. As respostas aparecem só para você.
2. Com uma conta sem "Gerenciar servidor", `/ponto-admin` não aparece.
3. Como admin: `/ponto-admin abertos`, `fechar`, `ajustar` e `relatorio`. O CSV abre no Excel/Sheets com acentos corretos.
4. `docker compose up -d --force-recreate`: as horas registradas continuam lá (PNT-18).
5. Com um `PONTO_GUILD_ID` de um servidor sem o bot, o log mostra a mensagem de PNT-17.

## Fora de escopo

- Projetos, clientes e valor/hora (decisão do dono: só horas totais).
- Lançamento manual de horas pelo freela (só o admin ajusta).
- Edição ou exclusão de uma sessão específica (a correção é por ajuste).
- Visibilidade pública das horas.
- Interface web ou exportação automática para planilha.

## Questões em aberto

- [ ] Criar um comando `/ajuda` com o resumo de uso dentro do Discord.
- [ ] Rotina de backup automático do `ponto.db` na VPS.
- [ ] Testes automatizados da camada do Discord (cogs), hoje cobertos por teste de fumaça manual.

## Rastreabilidade

| Requisito | Código | Teste |
|---|---|---|
| PNT-01 | `ponto/service.py` → `TimeClock.clock_in`; `ponto/bot/freela.py` → `entrar` | `tests/test_ponto.py::TimeClockTest.test_clock_in_and_out` |
| PNT-02 | `TimeClock.clock_in`; índice único `one_open_session` em `ponto/repository.py` | `::test_cannot_clock_in_twice`, `::test_users_and_servers_are_independent` |
| PNT-03 | `TimeClock.pause`, `TimeClock.resume`; `Session.worked_seconds` | `::test_pauses_are_not_counted`, `::test_pause_rules` |
| PNT-04 | `TimeClock.clock_out`; `freela.sair`; `timeutil.format_duration` | `::test_pauses_are_not_counted`, `::test_clock_out_without_open_session`; `::TimeUtilTest.test_format_duration` |
| PNT-05 | `freela.status`; `service.describe` | manual |
| PNT-06 | `freela.horas`; `TimeClock.sessions`, `TimeClock.adjustments`, `TimeClock.totals` | manual |
| PNT-07 | `ponto/bot/admin.py` → `AdminCog` (`default_permissions(manage_guild=True)`) | manual |
| PNT-08 | `admin.relatorio`, `AdminCog._csv`; `TimeClock.totals` | `::test_report_is_sorted_by_total`; CSV manual |
| PNT-09 | `admin.ajustar`; `TimeClock.adjust`; `timeutil.parse_duration` | `::test_adjustments_add_to_totals`; `::TimeUtilTest.test_parse_duration` |
| PNT-10 | `admin.fechar`; `TimeClock.clock_out(at=…)`; `timeutil.parse_clock_time` | `::test_admin_closes_forgotten_session_in_the_past`, `::test_close_time_must_be_between_start_and_now`; `::TimeUtilTest.test_parse_clock_time_uses_previous_day_when_in_future` |
| PNT-11 | `admin.abertos`; `TimeClock.open_sessions` | `::test_users_and_servers_are_independent` |
| PNT-12 | `TimeClock.totals`; `SQLiteRepository.closed_sessions` | `::test_open_sessions_do_not_count_until_closed`, `::test_sessions_count_in_the_period_they_started`, `::test_adjustments_add_to_totals` |
| PNT-13 | `ponto/timeutil.py` → `period`, `PERIODS` | `::TimeUtilTest.test_periods` |
| PNT-14 | `TimeClock.sessions_to_remind`, `mark_reminded`; `ponto/bot/client.py` → `remind_open_sessions` | `::test_reminder_once_for_long_open_sessions` |
| PNT-15 | `ephemeral=True` e `@app_commands.guild_only()` nos cogs | manual |
| PNT-16 | `ponto/bot/ui.py` → `reply_error`; `cog_app_command_error` | manual |
| PNT-17 | `client.PontoBot.setup_hook` → `SetupError`; `ponto/__main__.py` | manual |
| PNT-18 | `SQLiteRepository`; volume `ponto-data` em `docker-compose.yml` | manual |

## Histórico

| Data | Mudança |
|---|---|
| 2026-09-29 | Implementação inicial |
| 2026-09-29 | PNT-17: mensagem acionável quando o bot não está no servidor ou o token é inválido; `PONTO_LOG_LEVEL` |
| 2026-09-30 | Spec retroativa escrita na adoção do SDD |

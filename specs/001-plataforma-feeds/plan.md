# 001. Plataforma de feeds: Plano técnico

| | |
|---|---|
| **Spec** | [spec.md](spec.md) |

## Visão geral

Um pacote Python (`feeds/`) com uma classe base abstrata, `Integration`, que implementa o fluxo inteiro (*template method*). Cada integração é uma subclasse que responde só a perguntas específicas: onde buscar, como identificar um item, como montar a mensagem. Um job do GitHub Actions roda `python -m feeds all` de hora em hora e versiona o estado no próprio repositório.

```
fetch()  ──►  já enviado? (SeenStore + keys())  ──►  enrich()  ──►  skip_reason()?  ──►  to_embed()  ──►  DiscordWebhook
                    ▲                                                                                        │
                    └───────────────────────────── state.save() ◄───────────────────────────────────────────┘
```

1. `fetch(full, limit)`: itens do mais antigo para o mais novo. `full=True` na primeira execução e no `--test` (busca mais profunda).
2. Filtra pelas `keys()` já presentes no estado. Na primeira execução, aplica o `bootstrap()`.
3. `enrich(item)`: só para itens novos (buscas caras, como PDFs, ficam aqui).
4. `skip_reason(item)`: se houver motivo, marca como visto e não publica.
5. `to_embed(item)` → `DiscordWebhook.send_embed`.
6. `state.save()` no `finally`.

## Componentes

| Componente | Responsabilidade | Arquivo |
|---|---|---|
| `Integration` | Fluxo completo; ganchos abstratos (`fetch`, `keys`, `label`, `to_embed`, `summary`) e opcionais (`enrich`, `bootstrap`, `skip_reason`) | `feeds/core/integration.py` |
| `SeenStore` | Conjunto de chaves já enviadas, salvo como lista JSON ordenada; `is_new` indica a primeira execução | `feeds/core/state.py` |
| `DiscordWebhook` | Envio de embeds, `allowed_mentions` vazio, novas tentativas em 429 | `feeds/core/discord.py` |
| `HttpClient` | GET/POST sobre `urllib` com User-Agent e timeout | `feeds/core/http.py` |
| `clock` | `BRT` e `today()` | `feeds/core/clock.py` |
| `config` | `.env`, `require_env`, `ConfigError` | `feeds/core/config.py` |
| CLI | Argumentos, execução isolada por integração, código de saída | `feeds/__main__.py` |
| Registro | `INTEGRATIONS = {slug: classe}` | `feeds/integrations/__init__.py` |
| Agendamento | Cron, testes, publicação e commit do estado | `.github/workflows/feeds.yml` |

## Modelo de dados

- **Estado**: `state/<slug>.json` é uma lista ordenada de strings (chaves). Cada integração decide suas chaves (IDs, links, título normalizado…). Um item é "visto" se **qualquer** chave dele estiver no conjunto.

## Decisões

| # | Decisão | Alternativas descartadas | Motivo |
|---|---|---|---|
| D1 | Estado em JSON **commitado no repositório** pelo próprio workflow | Banco externo; cache do Actions; artefatos | O Actions não guarda nada entre execuções. O git é gratuito, auditável (dá para ver o que foi enviado em cada commit) e simples de corrigir à mão. Custo: se o push falhar, a próxima execução reenvia (mitigado por FEED-13). |
| D2 | Várias chaves por item | Uma chave única | Fontes mudam de identificador (a busca da Agência usava link, o feed usa `?p=ID`) e a mesma missão aparece em fontes diferentes. Qualquer chave coincidente basta para deduplicar. |
| D3 | *Template method* com ganchos opcionais | Cada integração com o próprio laço | Garante o mesmo comportamento de deduplicação, dry-run e teste em todas; uma integração nova só implementa o específico. |
| D4 | `skip_reason` marca o item como visto | Reavaliar a cada execução | Evita baixar PDFs toda hora para missões encerradas. Custo aceito: um prazo prorrogado depois de encerrado não reabre o item. |
| D5 | Execução de hora em hora | Diária; a cada 5 min | O conteúdo muda poucas vezes por semana; uma hora dá boa latência e cabe folgado nos minutos gratuitos do Actions. |
| D6 | `urllib` em vez de `requests` | `requests`/`httpx` | Constituição C6: menos dependências no CI. |

## Verificação da constituição

| Princípio | Como é atendido |
|---|---|
| C1 Não fazer spam | Deduplicação por múltiplas chaves (FEED-02), `bootstrap` (FEED-03), estado salvo mesmo em falha (FEED-07) e push com novas tentativas (FEED-13) |
| C2 Não postar errado | Integrações lançam exceção quando o formato da fonte é desconhecido; a CLI isola a falha (FEED-09) |
| C3 Testável sem rede | `tests/test_integration.py` usa uma integração falsa e um webhook falso |
| C4 Segredos | Webhooks via env/secrets (FEED-11) |
| C5 Horário de Brasília | `feeds/core/clock.py` |
| C6 Dependências | CI instala só `requirements.txt`; os testes rodam com `discover -s tests` e não importam o bot |
| C7 Privacidade | `allowed_mentions` vazio (FEED-10) |

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Push do estado falha | Mensagens reenviadas na próxima hora | Novas tentativas com `pull --rebase`; job vermelho com aviso para corrigir o estado à mão |
| Cron desativado após 60 dias sem atividade | Integrações param em silêncio | Questão em aberto na spec |
| Alguém roda a execução normal localmente sem dar push no estado | Reenvio pelo Actions | Aviso no README; preferir `--dry-run` / `--test` localmente |

## Estratégia de teste

- **Unitário**: `tests/test_integration.py` cobre deduplicação, `bootstrap`, `skip_reason`, `--dry-run`, `--test` e o salvamento do estado.
- **Manual**: ver "Verificação manual" na spec.
- **Comando**: `python -m unittest discover -s tests -t .`.

## Adicionando uma integração

1. Escreva a spec (`specs/NNN-nome/spec.md`) e o plano a partir de [`_templates/`](../_templates/).
2. Crie `feeds/integrations/<nome>/` com uma subclasse de `Integration`:

   ```python
   class MinhaIntegracao(Integration[MeuItem]):
       slug = "minha"                         # nome na CLI e em state/minha.json
       title = "Minha integração"             # nome nos logs
       username = "Nome no Discord"
       webhook_env = "DISCORD_WEBHOOK_MINHA_URL"

       def fetch(self, *, full, limit): ...   # lista de itens, do mais antigo ao mais novo
       def keys(self, item): ...              # IDs únicos do item
       def label(self, item): ...             # texto curto para logs
       def to_embed(self, item): ...          # embed do Discord
       def summary(self, item): ...           # linhas do --dry-run
       # opcionais: enrich(item), bootstrap(items), skip_reason(item)
   ```

3. Registre a classe em `feeds/integrations/__init__.py` (`INTEGRATIONS`).
4. Adicione a variável no `.env.example`, o secret no GitHub e o `env:` no passo "Publicar no Discord" do workflow.

## Configuração e deploy

Ver [README › Feeds](../../README.md#feeds-github-actions).

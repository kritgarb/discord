# Missões Sebrae/SE → Discord

Acompanha as **missões empresariais** publicadas na [Agência Sebrae de Notícias (SE)](https://se.agenciasebrae.com.br/) e posta cada missão nova num canal do Discord, com as informações principais:

| Campo | Exemplo |
|---|---|
| 🎯 Evento | Deep Tech Summit 2026 |
| 📍 Local | São Paulo/SP |
| 📅 Data | 11 a 12 de agosto de 2026 |
| 💰 Valor (participante) | ≈ R$ 2.500,00 |
| ⏰ Inscrições até | 30/06/2026 |

O card também traz links para a notícia, o edital e o formulário de inscrição.

Roda de hora em hora no GitHub Actions e **só posta missões que ainda não foram enviadas**.

## Como funciona

```
feed RSS  ──►  filtra títulos com "missão/missões"  ──►  já enviada? (posted.json)
                                                               │ não
                                                               ▼
               página da notícia  +  edital (PDF)  ──►  extrai os campos  ──►  webhook do Discord
```

1. **Busca** — lê o feed principal `https://se.agenciasebrae.com.br/feed/` (3 páginas ≈ 30 posts por execução; na primeira execução, até 30 páginas).
2. **Filtra** — mantém só posts cujo título contém *missão/missões*.
3. **Deduplica** — ignora o que já está no `posted.json`.
4. **Extrai** os detalhes de cada missão nova:

   | Campo | Fonte |
   |---|---|
   | Evento, local, data | 1º parágrafo da notícia (*"levará empreendedores à X, …, que acontecerá na cidade de Y, no período de Z"*); se faltar, preâmbulo do edital |
   | Valor | item 10.1 do edital (*"O valor a ser pago pelo participante… R$ X"*) |
   | Prazo de inscrição | a **data mais recente** entre: período de inscrição da notícia, prorrogações (*"prorrogado até…"*) e item 8.3 do edital mais novo (erratas) |
   | Edital | último link de PDF com "edital" no post (erratas vêm depois do original) |
   | Inscrição | link `forms.office.com` do post |

5. **Posta** um card por missão, da mais antiga para a mais nova, e registra no `posted.json`.

Campos que não forem encontrados são omitidos do card. Se quase nada for encontrado (ex.: notícia que não segue o modelo padrão), o card mostra o resumo da notícia.

### Controle do que já foi enviado

O `posted.json` guarda, para cada missão enviada, o `guid` do RSS (`?p=ID`) **e** o link da notícia. Se qualquer um dos dois já estiver lá, a missão não é enviada de novo.

No GitHub Actions, o próprio workflow faz commit do `posted.json` depois de cada execução. **Não apague esse arquivo**: sem ele o script entende que é a primeira execução e posta todas as missões existentes de novo.

## Setup (GitHub Actions)

1. Crie um webhook no Discord: **Configurações do canal → Integrações → Webhooks → Novo webhook → Copiar URL**.
2. No repositório: **Settings → Secrets and variables → Actions → New repository secret**
   - Nome: `DISCORD_WEBHOOK_URL`
   - Valor: a URL do webhook
3. Se quiser rodar na hora: **Actions → Missões Sebrae/SE → Discord → Run workflow**.

O agendamento fica em [`.github/workflows/missoes.yml`](.github/workflows/missoes.yml) (`cron: "0 * * * *"`, de hora em hora, em UTC). O GitHub pode atrasar execuções agendadas em alguns minutos, e desativa o cron em repositórios sem atividade por 60 dias; nesse caso é só reativar na aba Actions.

## Rodando local

Requer Python 3.9+.

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha a URL do webhook. O `.env` está no `.gitignore` e nunca vai para o repositório. No Actions, o valor vem do secret, que tem prioridade sobre o `.env`.

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### Comandos

| Comando | O que faz |
|---|---|
| `python sebrae_missoes.py` | Execução normal (a mesma do cron): posta só as missões novas e atualiza o `posted.json` |
| `python sebrae_missoes.py --dry-run` | Mostra no terminal o que seria postado, sem enviar nada |
| `python sebrae_missoes.py --test 3` | Posta as 3 missões mais recentes **mesmo que já enviadas**, sem alterar o `posted.json`. Para testar o visual do card |
| `python sebrae_missoes.py --test 3 --dry-run` | Mostra no terminal os campos extraídos das 3 mais recentes |

> ⚠️ Se rodar a execução normal localmente, faça commit e push do `posted.json` atualizado. Senão, o Actions não sabe o que já foi enviado e posta de novo.

## Configuração

Constantes no topo de [`sebrae_missoes.py`](sebrae_missoes.py):

| Constante | Padrão | Descrição |
|---|---|---|
| `FEED_URL` | `https://se.agenciasebrae.com.br/feed/` | Feed RSS de origem |
| `MISSION_RE` | `missão/missões` | Regex aplicada ao título para identificar missões |
| `PAGES_PER_RUN` | `3` | Páginas do feed lidas em cada execução normal |
| `MAX_PAGES_FIRST_RUN` | `30` | Páginas lidas na primeira execução (sem `posted.json`) ou no `--test` |
| `EMBED_COLOR` | `0x005EB8` | Cor da barra lateral do card |

## Limitações conhecidas

- **Não usamos a busca do site** (`?s=missão`): o índice dela está desatualizado e deixa missões de fora. O feed principal é completo.
- **O conteúdo do RSS pode estar desatualizado** (ex.: sem as prorrogações/erratas mais recentes). Por isso os detalhes são lidos direto da página da notícia.
- **O valor é aproximado**: é o que consta no edital, que avisa que pode mudar na contratação.
- **A extração depende do padrão de texto** das notícias e editais do Sebrae/SE. Se o modelo mudar, algum campo pode deixar de aparecer; o post continua sendo enviado com o que foi encontrado. Use `--test N --dry-run` para conferir.
- Se o edital estiver fora do ar ou não puder ser lido, o card sai sem valor, e o aviso aparece no log.

## Estrutura

```
.
├── sebrae_missoes.py           # script principal
├── posted.json                 # missões já enviadas (atualizado pelo workflow)
├── requirements.txt            # pypdf (leitura dos editais)
├── .env.example                # modelo de variáveis para rodar local
└── .github/workflows/
    └── missoes.yml             # cron de hora em hora no GitHub Actions
```

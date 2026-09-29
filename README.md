# Missões Sebrae/SE → Discord

Busca missões empresariais na [Agência Sebrae de Notícias (SE)](https://se.agenciasebrae.com.br/) pelo RSS da busca do site (`?s=missão&feed=rss2`), filtra pelo título e posta cada uma como card num canal do Discord via webhook.

Roda de hora em hora no GitHub Actions (`.github/workflows/missoes.yml`). O arquivo `posted.json` guarda o que já foi postado e é commitado pelo próprio workflow.

## Setup

1. No repositório: **Settings → Secrets and variables → Actions → New repository secret**
   - Nome: `DISCORD_WEBHOOK_URL`
   - Valor: a URL do webhook do canal
2. **Actions → Missões Sebrae/SE → Discord → Run workflow** para a primeira execução.

## Rodando local

Copie `.env.example` para `.env` e preencha `DISCORD_WEBHOOK_URL` (o `.env` não vai pro git). No Actions o valor vem do secret.

```bash
python sebrae_missoes.py --dry-run
```

```bash
python sebrae_missoes.py
```

Sem dependências externas, só a biblioteca padrão do Python 3.9+.

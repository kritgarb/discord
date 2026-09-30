# 003. Compilado do Código Fonte TV: Plano técnico

| | |
|---|---|
| **Spec** | [spec.md](spec.md) |

## Visão geral

O site roda na plataforma Pingback (Next.js). A home embute as 12 edições mais recentes no JSON `<script id="__NEXT_DATA__">`, com título, data de publicação, banner e slug. `Compilado` lê esse JSON numa única requisição, sem login e sem raspar HTML.

```
home ─► __NEXT_DATA__ ─► parse_home ─► Edition[] ─► (1ª execução: bootstrap marca < hoje) ─► novas ─► card
```

## Componentes

| Componente | Responsabilidade | Arquivo |
|---|---|---|
| `Compilado` | Integração: `keys` (`uid`), `bootstrap` (antes de hoje), card | `feeds/integrations/compilado/integration.py` |
| `CompiladoSite` | Baixa a home | `feeds/integrations/compilado/source.py` |
| `parse_home`, `split_title` | Funções puras de leitura do JSON e do título | `source.py` |
| `Edition` | Dataclass: `uid`, `name`, `title`, `link`, `published`, `image`, `headlines` | `feeds/integrations/compilado/models.py` |

## Decisões

| # | Decisão | Alternativas descartadas | Motivo |
|---|---|---|---|
| D1 | Ler o `__NEXT_DATA__` da home | Raspar o HTML; abrir cada edição | Uma requisição traz tudo de forma estruturada; as páginas das edições são pagas. |
| D2 | Manchetes a partir do título | Conteúdo da edição | O conteúdo é exclusivo para inscritos; o título já lista as manchetes separadas por ";". |
| D3 | `bootstrap` = edições anteriores a hoje | "Postar só se for de hoje" em toda execução | Com estado + `bootstrap`, uma edição publicada às 23h50 e vista à 00h00 não se perde. Na ativação, o histórico não é despejado. |
| D4 | Verificar de hora em hora | Um dia fixo da semana | As edições não têm dia fixo, e às vezes saem várias juntas. |
| D5 | Link da edição = home + slug | Montar pelo número do título | O número do título (#263) e o slug (`ep264`) não batem no próprio site; o slug é o que funciona. |

## Verificação da constituição

| Princípio | Como é atendido |
|---|---|
| C1 Não fazer spam | `bootstrap` na primeira execução; `uid` como chave |
| C2 Não postar errado | `parse_home` lança erro se não encontrar `__NEXT_DATA__` (CMP-03) |
| C3 Testável sem rede | `parse_home` recebe HTML; o teste de `bootstrap` fixa a data com `mock` |
| C4 Segredos | `DISCORD_WEBHOOK_COMPILADO_URL` |
| C5 Horário de Brasília | `bootstrap` compara em `BRT` |
| C6 Dependências | Só a biblioteca padrão |
| C7 Privacidade | Sem menções (FEED-10) |

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| A plataforma muda o formato do JSON | Integração para | Erro claro no log (CMP-03); as outras integrações seguem (FEED-09) |
| Mais de 12 edições entre duas execuções | Edições antigas não aparecem na home | Improvável (≈1 por semana, verificação por hora) |

## Estratégia de teste

- **Unitário** (`tests/test_compilado.py`): título, leitura da home com um JSON sintético e o `bootstrap` na virada do dia em Brasília.
- **Manual**: ver a spec.

## Configuração e deploy

- Secret `DISCORD_WEBHOOK_COMPILADO_URL` (canal do Compilado).
- Estado em `state/compilado.json`.

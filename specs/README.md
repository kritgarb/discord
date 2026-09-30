# Especificações

Este projeto segue **Spec Driven Development (SDD)**: a especificação é a fonte da verdade do comportamento. O código implementa a spec, e os testes provam que a implementação cumpre a spec.

Toda mudança de comportamento começa aqui, não no código.

## Índice

| ID | Feature | Status | Spec | Plano |
|---|---|---|---|---|
| — | Constituição (princípios do projeto) | Vigente | [constitution.md](constitution.md) | — |
| 001 | Plataforma de feeds | Implementada | [spec](001-plataforma-feeds/spec.md) | [plano](001-plataforma-feeds/plan.md) |
| 002 | Missões Sebrae/SE | Implementada | [spec](002-missoes-sebrae/spec.md) | [plano](002-missoes-sebrae/plan.md) |
| 003 | Compilado do Código Fonte TV | Implementada | [spec](003-compilado/spec.md) | [plano](003-compilado/plan.md) |
| 004 | Bot de ponto dos freelas | Implementada | [spec](004-bot-ponto/spec.md) | [plano](004-bot-ponto/plan.md) |

## Ciclo de uma feature

```
1. Especificar  →  2. Planejar  →  3. Quebrar em tarefas  →  4. Implementar + testar  →  5. Fechar
   spec.md          plan.md          tasks.md                 código + tests/               status + rastreabilidade
```

1. **Especificar** (`spec.md`): o **quê** e o **porquê**, sem falar de implementação. Contexto, histórias de usuário, requisitos numerados com critérios de aceite, fora de escopo e questões em aberto. Termina com status **Aprovada**.
2. **Planejar** (`plan.md`): o **como**. Componentes, fluxo de dados, decisões com alternativas descartadas, riscos e estratégia de teste. Precisa respeitar a [constituição](constitution.md).
3. **Tarefas** (`tasks.md`): passos pequenos e ordenados. Cada um referencia os requisitos que atende. Tarefas de teste vêm antes ou junto das de código.
4. **Implementar e testar**: cada requisito precisa de pelo menos um teste automatizado ou de uma verificação manual declarada na spec.
5. **Fechar**: preencha a tabela de **Rastreabilidade** da spec (requisito → código → teste), mude o status para **Implementada** e atualize o índice acima.

Features que já estavam prontas antes da adoção do SDD não têm `tasks.md`: o histórico está no git. As próximas features usam os três arquivos.

## Mudando uma feature existente

- **Edite a spec primeiro.** Para comportamento novo, crie um requisito com um **ID novo**. IDs nunca são reutilizados.
- **Requisito que deixou de valer:** marque como ~~riscado~~ com *(removido em AAAA-MM-DD: motivo)*. Não apague, para o histórico continuar legível.
- **Mudança de requisito existente:** atualize o texto e registre no **Histórico** da spec.
- Atualize o `plan.md` se o design mudar, e a rastreabilidade se testes ou código mudarem.

## Convenções

- **Requisitos no formato EARS**, em pt-BR:
  - *Ubíquo*: "O sistema DEVE …"
  - *Evento*: "QUANDO <gatilho>, o sistema DEVE …"
  - *Estado*: "ENQUANTO <condição>, o sistema DEVE …"
  - *Indesejado*: "SE <situação>, ENTÃO o sistema DEVE …"
  - *Opcional*: "ONDE <recurso existir>, o sistema DEVE …"
- **IDs** por feature: `FEED-nn`, `MIS-nn`, `CMP-nn`, `PNT-nn`.
- **Status de uma spec:** Rascunho → Aprovada → Implementada (→ Obsoleta).
- **Verificação:** cada requisito indica se é coberto por teste automatizado (`tests/...::Classe.test_x`) ou por verificação manual (com o passo a passo).
- **Templates:** [`_templates/`](_templates/).

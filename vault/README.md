# Crypto LawMap — Vault

Este vault é gerado automaticamente pelo pipeline em `../src/`. Cada nota `.md` é uma norma jurídica; o YAML frontmatter carrega o estado; os `[[wikilinks]]` formam o grafo.

## Como ler

| Campo | Significado |
|---|---|
| `id` | Identificador único: `{PAÍS}-{SLUG}-{ANO}` (ex.: `BR-LEI14478-2022`) |
| `country` | ISO alpha-2 (`INTL` para FATF, FSB, BIS, IOSCO...) |
| `type` | `statute` (lei) · `regulation` (regulamento) · `guidance` (orientação) · `case_law` (jurisprudência) |
| `status` | `discovered` → `verified` → `scraped` → `analyzed` (ou `quarantine`) |
| `discovered_via` | `seed` (descoberta inicial) · `citation` (citada por outra norma) · `semantic` (sugerida por similaridade) |
| `confidence` | 0–1; fonte primária (gov/regulador) + URL viva + título batendo = alto |
| `source_authority` | `primary` (gov/regulador) · `secondary` (agregador jurídico) · `tertiary` (mídia) |
| `cycle` | Em que iteração do loop a nota entrou |
| `references` | Lista de `[[wikilinks]]` para outras normas |
| `ref_types` | Para cada ref: `citation` (explícita) ou `semantic` (sugestão) |

## Estrutura de pastas

```
BR/    US/    SG/    ...    → uma pasta por país, com normas nacionais
INTL/                       → normas supranacionais (FATF, BIS, FSB...)
_MOC/                       → Maps of Content (índices por país, auto-gerados)
_meta/                      → run-log.md, budget-tracker.json
_quarantine/                → nós de baixa confiança (FORA do grafo principal)
```

## Comece pelo

- [[Dashboard]] — visão geral com Dataview
- [[_MOC/INDEX]] — índice global de países
- [[_meta/run-log]] — histórico de execuções, custo, convergência

## Plugins recomendados

| Plugin | Por quê |
|---|---|
| **Dataview** | obrigatório — todas as queries do Dashboard dependem dele |
| **Juggl** | visualização interativa do grafo (filtra por país/status/type ao vivo) |
| **Path Finder** | encontra caminhos entre 2 normas (ex.: "como a Lei BR conecta com FATF?") |
| **Folder Notes** | transforma os arquivos em `_MOC/` em landing pages das pastas |

> *Sobre centralidade:* o antigo **Graph Analysis** foi removido. O Dashboard já tem uma query Dataview que faz o mesmo trabalho (top hubs por inlinks).

## Edição manual

Você **pode** editar qualquer nota à mão (anotações, traduções, etc.). O pipeline não sobrescreve o corpo de uma nota com `status: analyzed` — só faz merge não-destrutivo de novos `references`. Mas evite mexer no frontmatter de campos como `id`, `country`, `status` (isso quebra dedup).

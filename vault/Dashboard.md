---
cssclasses: [dashboard]
---

# Crypto LawMap — Dashboard

> Requer o plugin **Dataview** instalado. As queries abaixo se preenchem sozinhas conforme o pipeline rodar.

---

## Estado geral

```dataview
TABLE WITHOUT ID
  country as "País",
  length(rows) as "Total",
  length(filter(rows, (r) => r.status = "analyzed")) as "✓ analyzed",
  length(filter(rows, (r) => r.status = "scraped"))  as "scraped",
  length(filter(rows, (r) => r.status = "verified")) as "verified",
  length(filter(rows, (r) => r.status = "quarantine")) as "🛑 quarantine"
FROM ""
WHERE country
GROUP BY country
SORT length(rows) DESC
```

---

## Distribuição por tipo

```dataview
TABLE WITHOUT ID
  type as "Tipo",
  length(rows) as "Total",
  length(filter(rows, (r) => r.discovered_via = "seed"))     as "seed",
  length(filter(rows, (r) => r.discovered_via = "citation")) as "citação",
  length(filter(rows, (r) => r.discovered_via = "semantic")) as "semântico"
FROM ""
WHERE type AND status != "quarantine"
GROUP BY type
SORT length(rows) DESC
```

---

## Top 10 hubs do grafo  *(normas mais citadas)*

```dataview
TABLE WITHOUT ID
  link(file.link, title) as "Norma",
  country as "País",
  type as "Tipo",
  length(filter(this.file.outlinks, (l) => false)) as "_"
FROM ""
WHERE status != "quarantine"
FLATTEN file.inlinks as inbound
GROUP BY file.link
SORT length(rows) DESC
LIMIT 10
```

> Dica: ative *Graph Analysis* → "Centrality" para uma medida mais sofisticada.

---

## Pontes supranacionais  *(normas INTL com inlinks de múltiplos países)*

```dataview
TABLE WITHOUT ID
  link(file.link, title) as "Norma INTL",
  regulator as "Órgão",
  length(filter(file.inlinks, (l) => true)) as "Incoming"
FROM "INTL"
WHERE status = "analyzed"
SORT length(file.inlinks) DESC
LIMIT 15
```

---

## Adicionadas no último ciclo

```dataview
TABLE WITHOUT ID
  link(file.link, title) as "Norma",
  country as "País",
  type as "Tipo",
  discovered_via as "Origem",
  cycle as "Ciclo"
FROM ""
WHERE cycle = max(rows.cycle) AND status != "quarantine"
GROUP BY cycle
SORT file.ctime DESC
LIMIT 20
```

---

## 🛑 Quarentena  *(baixa confiança — fora do grafo principal)*

```dataview
TABLE WITHOUT ID
  link(file.link, title) as "Norma",
  country as "País",
  source_url as "URL",
  confidence as "Conf.",
  source_authority as "Authority"
FROM "_quarantine"
SORT confidence DESC
LIMIT 25
```

---

## Por jurisdição

```dataview
LIST link(file.link, title) + " *(" + type + ")*"
FROM ""
WHERE status = "analyzed"
GROUP BY jurisdiction
SORT jurisdiction ASC
```

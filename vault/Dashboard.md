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
  length(filter(rows, (r) => r.status = "quarantine")) as "⚠ quarantine"
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

## Top 15 hubs do grafo  *(normas mais citadas — proxy de centralidade)*

```dataview
TABLE WITHOUT ID
  link(file.link, title) as "Norma",
  country as "País",
  type as "Tipo",
  length(file.inlinks) as "Inlinks"
FROM ""
WHERE status != "quarantine" AND length(file.inlinks) > 0
SORT length(file.inlinks) DESC
LIMIT 15
```

---

## Pontes supranacionais  *(normas INTL ordenadas por quantos países as citam)*

```dataview
TABLE WITHOUT ID
  link(file.link, title) as "Norma INTL",
  regulator as "Órgão",
  length(file.inlinks) as "Total inlinks"
FROM "INTL"
WHERE status = "analyzed" AND length(file.inlinks) > 0
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
WHERE status != "quarantine"
SORT cycle DESC, file.ctime DESC
LIMIT 20
```

---

## ⚠ Quarentena  *(baixa confiança — fora do grafo principal)*

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

---

## Receitas úteis

**Filtrar para um país específico:** abra qualquer query, mude `WHERE country` para `WHERE country = "BR"`.

**Caminho entre 2 normas:** com **Path Finder** instalado, abra a norma origem → comando `Path Finder: Find paths from this note` → selecione a destino.

**Visualização avançada do grafo:** comando `Juggl: Open Juggl` → permite filtrar por status, type, country interativamente.

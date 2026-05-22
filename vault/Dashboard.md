---
cssclasses: [dashboard]
---

# Crypto LawMap — Dashboard

> Requires the **Dataview** plugin. Queries below populate themselves as the pipeline runs.

---

## Overall state

```dataview
TABLE WITHOUT ID
  country as "Country",
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

## Distribution by type

```dataview
TABLE WITHOUT ID
  type as "Type",
  length(rows) as "Total",
  length(filter(rows, (r) => r.discovered_via = "seed"))     as "seed",
  length(filter(rows, (r) => r.discovered_via = "citation")) as "citation",
  length(filter(rows, (r) => r.discovered_via = "semantic")) as "semantic"
FROM ""
WHERE type AND status != "quarantine"
GROUP BY type
SORT length(rows) DESC
```

---

## Top 15 graph hubs  *(most-cited norms — centrality proxy)*

```dataview
TABLE WITHOUT ID
  link(file.link, title) as "Norm",
  country as "Country",
  type as "Type",
  length(file.inlinks) as "Inlinks"
FROM ""
WHERE status != "quarantine" AND length(file.inlinks) > 0
SORT length(file.inlinks) DESC
LIMIT 15
```

---

## Supranational bridges  *(INTL norms ranked by how many jurisdictions cite them)*

```dataview
TABLE WITHOUT ID
  link(file.link, title) as "INTL norm",
  regulator as "Body",
  length(file.inlinks) as "Inlinks"
FROM "INTL"
WHERE status = "analyzed" AND length(file.inlinks) > 0
SORT length(file.inlinks) DESC
LIMIT 15
```

---

## Added in the latest cycle

```dataview
TABLE WITHOUT ID
  link(file.link, title) as "Norm",
  country as "Country",
  type as "Type",
  discovered_via as "Source",
  cycle as "Cycle"
FROM ""
WHERE status != "quarantine"
SORT cycle DESC, file.ctime DESC
LIMIT 20
```

---

## ⚠ Quarantine  *(low confidence — excluded from the main graph)*

```dataview
TABLE WITHOUT ID
  link(file.link, title) as "Norm",
  country as "Country",
  source_url as "URL",
  confidence as "Conf.",
  source_authority as "Authority"
FROM "_quarantine"
SORT confidence DESC
LIMIT 25
```

---

## By jurisdiction

```dataview
LIST link(file.link, title) + " *(" + type + ")*"
FROM ""
WHERE status = "analyzed"
GROUP BY jurisdiction
SORT jurisdiction ASC
```

---

## Useful recipes

**Filter to one country:** open any query and change `WHERE country` to `WHERE country = "BR"`.

**Path between two norms:** with **Path Finder** installed, open the source norm → command `Path Finder: Find paths from this note` → pick the destination.

**Advanced graph exploration:** command `Juggl: Open Juggl` → filter interactively by status, type, country.

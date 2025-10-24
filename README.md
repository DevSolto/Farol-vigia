# Farol do Nordeste

> Plataforma de coleta (scraping), catalogação (cidades & pessoas) e análise de notícias regionais.

---

## 1) Visão Geral

**Missão**: centralizar notícias de blogs/portais do Nordeste, extrair entidades (cidades — IBGE — e pessoas) e oferecer APIs para consultas, painéis e automações.

**Stack macro**:

* **farol-scraper** (Python): scraping + NER básico → publica eventos.
* **farol-api** (NestJS): autenticação, CRUD de fontes & pessoas, consultas de artigos/menções, consumo de eventos.
* **MongoDB**: armazenamento primário.
* **Redis Streams** (ou RabbitMQ/Kafka): fila/event bus.
* **(Opcional)** Prefect/cron: orquestração de execuções.

---

### Decisões-chave

* **Idempotência**: `url_canonical` e `fingerprint` por artigo; `article_id+entity_id` por menção.
* **Separação de papéis**: Scraper faz coleta/normalização; API governa entidades/menções, autenticação e consumo de eventos.
* **Polidez de scraping**: robots.txt, rate limit por host, ETag/Last-Modified, backoff com jitter.

---

## 2) Componentes

### 2.1 farol-scraper (Python)

* Estratégias por fonte em ordem: **RSS/Atom → Sitemap → Listagem (CSS) → AMP → Headless**.
* Normalização de URL (canonical, remoção de tracking) e data (ISO-8601 com offset, tz da fonte: default America/Recife).
* Extração de conteúdo (metas OG, seletores; fallback de legibilidade).
* Entidades:

  * **Cidades**: gazetteer IBGE (nome, UF, código)
  * **Pessoas**: NER com spaCy pt e pós-processamento (aliases/slug)
* Saída: gravação em `articles` + publicação de `ArticleIngested`.

### 2.2 farol-api (NestJS)

* **Auth**: JWT (access/refresh), Argon2, RBAC (`admin`, `editor`, `viewer`).
* **CRUD**: `sources` (blogs), `entities` (pessoas/cidades), `mentions`, `articles` (consulta).
* **Consumer**: lê `ArticleIngested`, cria/upserta `entities` e `mentions`.
* **Relatórios**: endpoints para estatísticas (top cidades, pessoas, fontes).

### 2.3 Banco & Fila

* **MongoDB**: coleções e índices descritos abaixo.
* **Redis Streams** (ou RabbitMQ/Kafka): confiabilidade e desacoplamento.

---

## 3) Esquemas de Dados (Mongo)

### 3.1 `sources`

* `_id: string` (slug único)
* `name, base_url, tz, active`
* `strategy_priority: ["rss","sitemap","listing","amp","headless"]`
* `selectors`: `{ listing_article, listing_title, listing_url, listing_summary, article_content, article_date, ... }`
* `pagination, date_format, locale, cleanup_rules, limits, policies`
* **Índices**: `_id` único; `active`

### 3.2 `articles`

* `source_id, url_original, url_canonical, fingerprint`
* `title, summary, content_text, content_html?`
* `published_at, scraped_at, lang, lead_image, authors[], tags[]`
* `status (ok|skipped_dupe|error), error_code, error_detail`
* **Índices**: `source_id+url_canonical (unique)`, `published_at (desc)`, `fingerprint`

### 3.3 `entities`

* `_id: "city:{ibge}" | "person:{slug}"`
* `type: city|person, name, aliases[]`
* `metadata`: `{ ibge, uf }` para city; `{ external_refs? }` para person
* `tracked: boolean`
* **Índices**: `type+name`, `tracked`

### 3.4 `mentions`

* `article_id(ObjectId)`, `entity_id(string)`, `entity_type`, `name`
* `metadata` (city: `{ibge, uf}`, person: `{confidence}`)
* `created_at`
* **Índices**: `entity_id`, `entity_type`, `article_id+entity_id (unique)`

### 3.5 `jobs`

* `flow, source_id, started_at, ended_at, stats{ fetched, inserted, dupes, errors }, errors[]`

### 3.6 `users` (Nest)

* `email(unique), name, password_hash, roles[], status, created_at`

### 3.7 `audit_logs`

* `when, who, action, payload`

---

## 4) Esquemas de Eventos

### 4.1 `ArticleIngested`

* `article_id (ObjectId)`, `source_id`, `published_at`
* `cities: [{ name, uf, ibge }]`
* `people: [{ name, slug, confidence }]`
* `pipeline_version`
* **Idempotência**: chave lógica por `article_id` + `pipeline_version`

### 4.2 `ReprocessRequest`

* `article_id` **ou** `source_id` + `date_range`
* `reason`, `requested_by`

---

## 6) API (Nest) — Contratos

**Prefixo**: `/api/v1`

### Auth

* `POST /auth/login` → `{ access_token, refresh_token }`
* `POST /auth/refresh` → `{ access_token }`

### Sources (blogs)

* `GET /sources?active=true`
* `POST /sources` (admin)
* `PATCH /sources/:id` (admin)
* `POST /sources/:id/sync` (admin) → enfileira execução

### Entities

* `GET /entities?type=person|city&tracked=true&q=...`
* `GET /entities/:id`
* `POST /entities` (criar pessoa manual)
* `PATCH /entities/:id` (aliases, tracked)

### Articles

* `GET /articles?source_id&date_from&date_to&city_ibge&person_id&q&has_people&has_cities&sort=published_at:desc`
* `GET /articles/:id` (inclui entidades relacionadas)

### Mentions

* `GET /mentions?entity_id&entity_type&date_from&date_to&source_id`

### Admin

* `GET /metrics/ingestion?source_id`
* `GET /jobs?source_id&date_from&date_to`
* `POST /admin/reprocess/article/:id`

**Padrões de resposta**: `{ data, meta{ pagination }, links }`. Erros: `{ error{ code, message, details } }`.

---

## 7) Autenticação & Segurança

* **JWT**: access (15m), refresh (7–30d)
* **Hash**: Argon2
* **RBAC**: guards por rota (`viewer`, `editor`, `admin`)
* **Rate limit**: por IP e rotas admin
* **CORS**: somente domínios do front
* **Audit**: todas operações de escrita
* **Validação**: DTOs rígidos (limitar regex de seletores)

---

## 8) Scraping — Políticas Operacionais

* **Respeito a robots.txt** e `Crawl-Delay`
* **User-Agent**: "FarolBot/1.0 (+URL de contato)"
* **Rate limit por host** (1–3 req/s) e **concurrency** controlada
* **HTTP condicional**: ETag / If-Modified-Since
* **Fallbacks**: AMP e Headless (Playwright) com **budget** (≤10% URLs/exec)
* **Datas**: prioridade para `article:published_time`; sempre salvar ISO-8601 com offset da fonte
* **Qualidade mínima**: `content_text_len >= N`; `published_at` plausível; linguagem `pt`

---

## 9) Catálogo IBGE & NER

* **Cidades**: snapshot IBGE versionado (nome, UF, código, aliases); normalização sem acentos; match por fronteiras de palavra; desambiguação por UF.
* **Pessoas**: spaCy pt com pós-processamento (slug/aliases); `confidence` em menções; `tracked=false` por padrão.

---

## 10) Observabilidade

* **Logs JSON** com trace-id (scraper ↔ API ↔ eventos)
* **Métricas** (Prometheus/OpenTelemetry):

  * Ingestão: sucesso/erro por fonte, latências p50/p95, % fallback headless, reprocessos
  * API: latência por rota, taxa de erro, cache hits
* **Alertas**:

  * queda de novos artigos
  * aumento de `parse_error`/`329`
  * lag na fila (mensagens não consumidas)

---

## 11) Deploy & Ambientes

### Dev (Docker Compose)

* Serviços: Mongo, Redis, farol-api, farol-scraper, (opcional) Prefect UI
* Volumes para dados e hot-reload nos apps

### Prod (Kubernetes)

* Deployments separados (API, Scraper)
* HPA do Scraper por lag da fila
* Secrets via Secret Manager / ExternalSecrets
* Backups de Mongo (cronjobs) e monitoramento

---

## 12) Variáveis de Ambiente (resumo)

* **farol-scraper**: `MONGO_URI`, `EVENT_BUS_URL`, `SCRAPER_UA`, `SCRAPER_RATE`, `SCRAPER_HEADLESS_BUDGET`, `TZ_DEFAULT=America/Recife`
* **farol-api**: `MONGO_URI`, `EVENT_BUS_URL`, `JWT_SECRET`, `JWT_EXP`, `REFRESH_EXP`, `CORS_ORIGINS`

---

## 13) Roadmap (MVP → V1)

**MVP**

1. CRUD de `sources` (Nest) + Auth (JWT)
2. Scraper com RSS+Sitemap; grava `articles`; publica `ArticleIngested`
2. Consumer (Nest) cria `entities/mentions`
3. Endpoints de consulta (filtros por cidade/pessoa/fonte)
4. Métricas básicas e índices Mongo

**V1**
6. Listing/AMP/Headless com budget
7. Cache/condicional HTTP; dashboards de ingestão
8. Watchlist de pessoas (tracked) + aliases
9. Reprocess por artigo/fonte; versionamento de pipeline
10. Alertas de quebra por fonte

---

## 13) ADRs (índice sugerido)

* ADR-001: Fila — Redis Streams vs RabbitMQ vs Kafka
* ADR-002: Topologia — quem grava `mentions/entities` (Scraper vs API)
* ADR-003: Estratégia de scraping por prioridade
* ADR-003: Política de headless e orçamento
* ADR-005: Identidade do artigo (canonical + fingerprint)

---

## 15) Contribuição

* Padrão de branches: `main` (proteção), `feat/*`, `fix/*`
* PRs com checklist (testes, docs atualizadas)
* Lint/format nos dois serviços

## 16) Qualidade de Código

Para rodar as ferramentas locais instale as dependências de desenvolvimento:

```bash
pip install .[dev]
```

Em seguida execute:

* **Ruff** (lint):

  ```bash
  ruff check .
  ```

* **Black** (formatação):

  ```bash
  black .
  ```

* **Mypy** (type-check estrito):

  ```bash
  mypy .
  ```

* **Pytest** (testes unitários e de integração):

  ```bash
  pytest
  ```

## 17) Licença

A definir (ex.: MIT ou Apache-2.0).

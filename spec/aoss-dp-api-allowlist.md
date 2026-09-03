# AOSS Data-Plane API Allowlist (Customer-Facing)

**Authoritative source:** `AWSSearchServicesJunoAPIParserV2/doc/APIs.md` (mainline) — the ext_authz path→`aoss:`-action authorization map that the Service Gateway enforces on every AOSS collection data-plane request.
- Code: https://code.amazon.com/packages/AWSSearchServicesJunoAPIParserV2/blobs/mainline/--/doc/APIs.md
- SigV4 signing: service name **`aoss`** (NOT `es`), against the collection endpoint.
- This is the codegen source of truth for an AOSS data-plane client. The AWS public doc ([serverless-genref.html](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-genref.html)) is a **strict subset**; the SGW Envoy route table is NOT the allowlist (its catch-all is too permissive).

## Legend
- *(no marker)* — GA, listed in the public AWS supported-operations doc → ship in external client.
- ⚠️ — customer SigV4 can reach it, but it is **not** in the public AWS doc (undocumented/preview) → optional, mark as such.
- 🔒 — internal / service-principal-only or force-denied for customer requests → **do NOT ship in an external client.**

Path notation is verbatim from the parser: `<index>` / `<any-thing>` / `<list-wc-all>` / `{index_name}` = path variables; query-string variants (`?provision=true`) preserved.

---

## Row count summary

| Category | Rows | Ship in external client |
|---|---|---|
| GA (public docs) | ~176 | ✅ |
| ⚠️ Customer-reachable, undocumented | ~17 | Optional (mark preview) |
| 🔒 Internal / SP-only | 8 | ❌ exclude |
| **Total `aoss:` rows** | **201** | Net customer surface ≈ 193 |

> **The public surface spans multiple doc pages, not just one.** `serverless-genref.html` is the data-access-policy permission table; **snapshot** ops + `/_cat/recovery` are GA-documented on a *separate* page ([serverless-snapshots.html](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-snapshots.html)). When judging "documented", check all relevant pages — a single-page diff over-counts the undocumented set.

**Excluded (🔒):** FineTune ×4, `_predict/stream`, `_execute/stream`, `_md/mappings` ×2.
**Not in this list:** `ocm:` (15 rows) = separate Mneme service (`opensearch:` IAM + own endpoint, own client); `md:/cors:/ism:/ssm:/idx:/ic:/login:/dashboards:/saml:` (~100 rows) = internal/infrastructure, not customer-facing.

---

## aoss:ReadDocument (46) — upstream: Search

```
GET|POST   /_search
GET|POST   /<list-wc-all>/_search
GET|POST   /_count
GET|POST   /<list-wc-all>/_count
GET|POST   /_field_caps
GET|POST   /<list-wc-all>/_field_caps
GET|POST   /_msearch
GET|POST   /<list-wc-all>/_msearch
GET|POST   /_rank_eval
GET|POST   /<list-wc-all>/_rank_eval
GET|POST   /_validate/query
GET|POST   /<list-wc-all>/_validate/query
GET|POST   /_analyze
GET|POST   /<index>/_analyze
GET|POST   /_mget
GET        /<index>/_mget
POST       /<index-wc-all>/_mget
GET|HEAD   /<index>/_doc/<_id>
GET|HEAD   /<index>/_source/<_id>
GET|POST   /<index>/_explain/<id>
POST       /_plugins/_sql
POST       /_plugins/_sql/_explain
POST       /_plugins/_sql/close                            # ⚠️
POST       /_plugins/_ppl
POST       /_plugins/_ppl/_explain
POST       /<list-wc-all>/_search/point_in_time            # CreatePIT
GET        /_search/point_in_time/_all                     # ListPIT
DELETE     /_search/point_in_time
DELETE     /_search/point_in_time/_all
```

## aoss:WriteDocument (8) — upstream: Index

```
POST   /_bulk
POST   /<index>/_bulk
POST   /<index>/_doc
POST   /<index>/_create/<_id>                              # SEARCH collection type only
PUT    /<index>/_create/<_id>                              # SEARCH collection type only
POST   /<index>/_update/<_id>                              # SEARCH collection type only
PUT    /<index>/_doc/<_id>                                 # SEARCH collection type only
DELETE /<index>/_doc/<_id>
```

> Collection-type gating (SEARCH vs TIME_SERIES vs VECTORSEARCH) is enforced downstream at the metadata/data-plane layer, NOT in this parser.

## aoss:CreateIndex (1) / aoss:DeleteIndex (1) — upstream: Index / Metadata

```
PUT    /<index>                                            # CreateIndex
DELETE /<list-wc-all>                                      # DeleteIndex
```

## aoss:DescribeIndex (17) — upstream: Metadata

```
GET    /<list-wc-all>
HEAD   /{index_name}
GET    /_mapping
GET    /_mappings
GET    /<list-wc-all>/_mapping
GET    /<list-wc-all>/_mappings
GET    /_setting
GET    /_setting/<name>
GET    /_settings
GET    /_settings/<name>
GET    /<list-wc-all>/_settings
GET    /<list-wc-all>/_settings/<name>
GET    /{index_name}/_setting
GET    /{index_name}/_setting/{field_name}
GET    /_resolve/index/<list-wc>
GET    /_cat/indices
GET    /_cat/indices/{index_name}
```

## aoss:UpdateIndex (16) — upstream: Metadata

```
PUT|POST /_mapping
PUT|POST /<list-wc-all>/_mapping/
PUT|POST /<list-wc-all>/_mappings/
PUT|POST /_setting
PUT|POST /_settings
PUT|POST /<list-wc-all>/_setting
PUT|POST /<list-wc-all>/_settings
PUT|POST /_md/mappings                                     # 🔒 temporary internal metadata API
```

## aoss:DescribeCollectionItems (34)

```
# Metadata
GET    /_alias
GET    /_alias/<alias>
GET    /_aliases
GET    /<list-wc-all>/_alias/<alias>
GET    /{index_name}/_alias
HEAD   /_alias/<alias>
HEAD   /<list-wc-all>/_alias/<alias>
HEAD   /{index_name}/_alias
GET    /_cat/aliases
GET    /_cat/aliases/{alias_name}
GET    /_cat/templates
GET    /_cat/templates/<template_name>
GET    /_index_template
GET    /_index_template/<index-template>
HEAD   /_index_template/<name>
GET    /_component_template
GET    /_component_template/<component-template>
HEAD   /_component_template/<component-template>
# Index
GET    /_ingest/pipeline/<any-thing>
GET|POST /_ingest/pipeline/_simulate
GET|POST /_ingest/pipeline/<pipeline-id>/_simulate         # ⚠️
GET    /_cat/recovery                                      # GA (documented on snapshots page)
GET    /_cat/recovery/<index-name>                         # GA (documented on snapshots page)
# Search
GET    /_search/pipeline<any-thing>
# Oasis (flow_framework)
GET    /_plugins/_flow_framework/workflow/<any-thing>
GET    /_plugins/_flow_framework/workflow/_search_
GET    /_plugins/_flow_framework/workflow/_status
GET    /_plugins/_flow_framework/workflow/_steps
GET    /_plugins/_flow_framework/workflow/_step?workflow_step=<any-thing>
GET    /_plugins/_flow_framework/workflow/state/_search
POST   /_plugins/_flow_framework/workflow/_search
POST   /_plugins/_flow_framework/workflow/state/_search
```

## aoss:CreateCollectionItems (6)

```
POST   /_aliases
PUT    /_ingest/pipeline/<any-thing>
PUT    /_search/pipeline<any-thing>
POST   /_plugins/_flow_framework/workflow
POST   /_plugins/_flow_framework/workflow?provision=true
POST   /_plugins/_flow_framework/workflow/<any-thing>/_provision
```

## aoss:UpdateCollectionItems (11)

```
PUT|POST /<list-wc>/_alias/<alias>
PUT|POST /<list-wc>/_aliases/<alias>
PUT|POST /_component_template/<component-template>
PUT|POST /_index_template/<index-template>
PUT      /_plugins/_flow_framework/workflow/<any-thing>
PUT      /_plugins/_flow_framework/workflow/<any-thing>?reprovision=true
POST     /_plugins/_flow_framework/workflow/<any-thing>/_deprovision
```

## aoss:DeleteCollectionItems (7)

```
DELETE /<list-wc>/_alias/<alias>
DELETE /<list-wc>/_aliases/<alias>
DELETE /_component_template/<component-template-list-wc>
DELETE /_index_template/<index-template>
DELETE /_ingest/pipeline/<any-thing>
DELETE /_search/pipeline<any-thing>
DELETE /_plugins/_flow_framework/workflow/<any-thing>
```

## ML Resources — upstream: Oasis

### aoss:DescribeMLResource (17)
```
GET      /_plugins/_ml/models/<any-thing>
GET      /_plugins/_ml/model_groups/<any-thing>
GET      /_plugins/_ml/connectors/<any-thing>
GET      /_plugins/_ml/tasks/<any-thing>
GET|POST /_plugins/_ml/models/_search
GET|POST /_plugins/_ml/model_groups/_search
GET|POST /_plugins/_ml/connectors/_search
# memory_containers — ⚠️ entire family undocumented
GET      /_plugins/_ml/memory_containers/<any-thing>
GET|POST /_plugins/_ml/memory_containers/_search
GET      /_plugins/_ml/memory_containers/<any-thing>/memories/<any-thing>/<any-thing>
GET|POST /_plugins/_ml/memory_containers/<any-thing>/memories/<any-thing>/_search
POST     /_plugins/_ml/memory_containers/<any-thing>/memories/sessions/_search
```

### aoss:CreateMLResource (6)
```
POST   /_plugins/_ml/models/_register
POST   /_plugins/_ml/model_groups/_register
POST   /_plugins/_ml/connectors/_create
POST   /_plugins/_ml/memory_containers/_create                        # ⚠️
POST   /_plugins/_ml/memory_containers/<any-thing>/memories/sessions  # ⚠️
POST   /_plugins/_ml/memory_containers/<any-thing>/memories           # ⚠️
```

### aoss:UpdateMLResource (7)
```
PUT    /_plugins/_ml/models/
PUT    /_plugins/_ml/model_groups/<any-thing>
PUT    /_plugins/_ml/connectors/<any-thing>
POST   /_plugins/_ml/models/<name>/_deploy
POST   /_plugins/_ml/models/<name>/_undeploy
PUT    /_plugins/_ml/memory_containers/<any-thing>                              # ⚠️
PUT    /_plugins/_ml/memory_containers/<any-thing>/memories/<any-thing>/<any-thing>  # ⚠️
```

### aoss:DeleteMLResource (6)
```
DELETE /_plugins/_ml/models/<any-thing>
DELETE /_plugins/_ml/model_groups/<any-thing>
DELETE /_plugins/_ml/connectors/<any-thing>
DELETE /_plugins/_ml/tasks/<any-thing>
DELETE /_plugins/_ml/memory_containers/<any-thing>                              # ⚠️
DELETE /_plugins/_ml/memory_containers/<any-thing>/memories/<any-thing>/<any-thing>  # ⚠️
```

### aoss:ExecuteMLResource (2)
```
POST   /_plugins/_ml/models/<name>/_predict
POST   /_plugins/_ml/models/<name>/_predict/stream           # 🔒 OASis FeatureEnablementValidator FORBIDDEN for customers
```

## Agents — upstream: Oasis

```
POST     /_plugins/_ml/agents/_register                      # aoss:CreateAgent
GET      /_plugins/_ml/agents/<any-thing>                    # aoss:DescribeAgent
GET|POST /_plugins/_ml/agents/_search                        # aoss:SearchAgents
PUT      /_plugins/_ml/agents/<any-thing>                    # aoss:UpdateAgent
DELETE   /_plugins/_ml/agents/<any-thing>                    # aoss:DeleteAgent
POST     /_plugins/_ml/agents/<name>/_execute                # aoss:InvokeAgent
POST     /_plugins/_ml/agents/<name>/_execute/stream         # 🔒 aoss:InvokeAgent — internal AG-UI transport, FORBIDDEN for customers
```

## Snapshot — upstream: Index  (GA — documented at [serverless-snapshots.html](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-snapshots.html))

Customer-facing repo name is the fixed literal **`aoss-automated`** (AOSS takes automatic hourly snapshots; there is no create-snapshot API). Parser uses generic `<repo-name>`, but customers only ever use `aoss-automated`.

```
POST   /_snapshot/aoss-automated/<snapshot_id>/_restore      # aoss:RestoreSnapshot
GET    /_snapshot/aoss-automated/<snapshot_id>               # aoss:DescribeSnapshot
GET    /_snapshot/aoss-automated/_all                        # aoss:DescribeSnapshot (list all)
GET    /_cat/snapshots/aoss-automated                        # aoss:DescribeSnapshot — NO trailing slash (trailing / => 404)
```

## FineTune — upstream: Oasis  (🔒 backend implemented, but routed via `finetune` service-code; NOT launched as a customer data-access permission — exclude from external client)

```
GET    /_plugins/_finetune/tasks                             # aoss:ListFineTuneTasks
GET    /_plugins/_finetune/tasks/<any-thing>                 # aoss:DescribeFineTuneTask
POST   /_plugins/_finetune/tasks                             # aoss:CreateFineTuneTask
PUT    /_plugins/_finetune/tasks/<any-thing>                 # aoss:UpdateFineTuneTask
```

---

## Notes for client builders

1. **Two SigV4 service names, both `aoss`** for AOSS: control plane (`aoss.<region>.amazonaws.com`, SkyCrane, AWS SDK Smithy model) and data plane (collection endpoint, this list). Managed OpenSearch data plane uses `es` — getting the service name wrong = 403.
2. **Not supported on AOSS DP** (do not add): stored scripts `/_scripts`, `/_cluster/*`, `/_nodes/*`, `_reindex`, `_refresh`/`_flush`, most `_cat/*` beyond indices/aliases/templates/snapshots/recovery. `/_cat/indices` response has no `health`/`status` fields. Painless inline-only.
3. **Source-file format anomalies** to tolerate when parsing `doc/APIs.md`:
   - `POST /_plugins/_ppl/_explain` has an extra empty field (EventName blank, `PPLExplain` shifted).
   - `GET /_plugins/_ml/tasks/<any-thing>` and `POST /_plugins/_ml/model_groups/_register` have trailing spaces.
   - `GET /_cat/snapshots` has stray spaces after commas.
4. **OCM / Mneme** is a separate product: `POST /service/ocm/operation/<Op>`, `ocm:` internal routing tokens, customer IAM `opensearch:<Op>` on a `space/<spaceId>` ARN, separate `*.ocm.<region>.on.aws` endpoint (SigV4 vendor `opensearch`, not `aoss`). Build as a distinct client if needed.

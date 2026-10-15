<div align="center">

<img src="docs/screenshots/landing.jpg" alt="SENTINEL landing page: Risk intelligence with a memory" width="100%">

# SENTINEL

### Risk intelligence with a memory.

*Turns breaking financial headlines into quantified, explainable portfolio actions, by remembering what happened the last time.*

[![Demo video](https://img.shields.io/badge/Demo_video-YouTube_(unlisted)-C8102E?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/pd1bAzlHApU)
[![Slide deck](https://img.shields.io/badge/Deck-PDF_%C2%B7_7_slides-0B1020?style=for-the-badge)](docs/presentation.pdf)
[![Architecture](https://img.shields.io/badge/Architecture-diagram-0B1020?style=for-the-badge)](docs/architecture.png)

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Streams-DC382D?logo=redis&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/tests-139_passing-2FD4A8)
![Data](https://img.shields.io/badge/data-public_%26_synthetic_only-6C8CFF)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

</div>

---

# SENTINEL: Risk Intelligence With a Memory - S&P Global & Crisil Campus Hackathon

**Candidate Name:** Chaitenya Chand  
**College Email ID:** chaitenya013mca25@igdtuw.ac.in  
**College / Campus:** Indira Gandhi Delhi Technical University for Women (IGDTUW)  
**Demo Video Link:** [YouTube (unlisted)](https://youtu.be/pd1bAzlHApU)

## Contents

1. [Project Overview / Problem Statement & Approach](#1-project-overview--problem-statement--approach)
2. [Architecture & Tech Stack](#2-architecture--tech-stack)
3. [Dataset Used](#3-dataset-used)
4. [Quickstart & Installation](#4-quickstart--installation)
5. [Key Results & Domain Impact](#5-key-results--domain-impact)
6. [The terminal, view by view](#6-the-terminal-view-by-view) · [7. Slide deck](#7-slide-deck) · [8. Repository layout](#8-repository-layout) · [9. API](#9-api) · [10. Tests](#10-tests) · [11. Limitations](#11-limitations--responsible-use) · [12. License](#12-license)

---

## 1. Project Overview / Problem Statement & Approach

Banks and asset managers drown in unstructured text: news, filings and social posts that move markets faster than
people can read. In the held-out sample used here, only **29 of 150** hand-labelled headlines (19%) were risk-relevant,
so analysts spend their day triaging noise, and the alerts they do get have **no memory**: a sentiment tool can say a
headline is negative, but not what markets did the last time something similar happened, or what it would do to *this* portfolio.

SENTINEL is an AI/NLP risk engine built around one loop with four verbs:

| | Verb | What happens |
|---|---|---|
| 1 | **Detect** | A hybrid relevance gate (MiniLM embeddings + logistic regression + rules), FinBERT sentiment (-1 to 1), an 8-class event type and an integrity score turn each headline into a signal with an impact of 1 to 10. |
| 2 | **Remember** | **PRECEDENT** matches the live event to similar past events (point-in-time, no look-ahead) and shows what markets did over the next 20 days, with sample sizes and shrinkage for thin history. |
| 3 | **Quantify** | **Stress Lab** converts the calibrated shocks into a full revaluation of a 109-holding wholesale book: VaR / ES, Shapley attribution, reverse stress and trigger rules. |
| 4 | **Act** | **Adaptive Index** tilts a 15-stock index toward the signals inside strict limits (caps, floor, turnover). Auto-apply or portfolio-manager approval. Every decision lands in a SHA-256 hash-chained **audit ledger**. |

<div align="center">
<a href="https://youtu.be/pd1bAzlHApU">
<img src="docs/youtube-thumbnail.png" alt="Watch the 4-minute cinematic walkthrough" width="70%">
</a>
<br><sub>Click to watch the 4-minute cinematic walkthrough (YouTube, unlisted).</sub>
</div>

## 2. Architecture & Tech Stack

![SENTINEL architecture](docs/architecture.png)

*High-resolution original: [`docs/architecture.png`](docs/architecture.png). Diagram sources (SVG + generator scripts): [`docs/diagrams/`](docs/diagrams/).*

### System flow

```mermaid
flowchart LR
    subgraph SRC["Public sources"]
        G["GDELT GKG<br/>news themes"]
        R["Publisher RSS"]
        E["SEC EDGAR 8-K"]
        S["Bluesky · Reddit"]
        P["Yahoo Finance · FRED<br/>prices, rates, VIX"]
    end
    subgraph ING["Ingest and NLP"]
        D["Connectors<br/>dedupe, time-stamp"]
        REL["Relevance gate<br/>MiniLM + LR + rules"]
        EV["Event classifier<br/>8 types"]
        SE["FinBERT sentiment"]
        IN["Integrity score"]
    end
    subgraph PLAT["Platform"]
        RS[("Redis Streams<br/>stream:signals")]
        PG[("PostgreSQL 16<br/>signals, prices, ledger")]
    end
    subgraph INT["Intelligence engines"]
        PR["PRECEDENT<br/>point-in-time analogs"]
        IM["Impact model<br/>8-K abnormal returns"]
        GRI["Global Risk Index"]
        SL["Stress Lab<br/>VaR, ES, Shapley"]
        AI["Adaptive Index<br/>capped tilts"]
    end
    API["FastAPI<br/>REST + WebSocket"]
    UI["React terminal<br/>9 live views"]
    AU[("SHA-256<br/>audit ledger")]

    G & R & E & S --> D --> REL --> EV --> SE --> IN --> RS
    P --> PG
    RS --> PG
    RS --> PR --> SL
    RS --> IM
    RS --> GRI
    PR --> AI
    GRI --> SL
    SL --> AU
    AI --> AU
    PG --> API
    SL --> API
    AI --> API
    GRI --> API
    API --> UI
```

### From headline to action

```mermaid
sequenceDiagram
    autonumber
    participant N as News / filing
    participant W as Scoring worker
    participant R as Redis Streams
    participant P as PRECEDENT
    participant S as Stress Lab
    participant A as Adaptive Index
    participant L as Audit ledger
    participant T as Terminal (WebSocket)

    N->>W: raw headline
    W->>W: relevance gate, event type, sentiment, integrity
    alt not relevant
        W-->>N: dropped as noise
    else relevant
        W->>R: publish signal (impact 1-10)
        R->>P: find similar past events
        P-->>R: analogs, forward-return bands, shock vector
        R->>T: signal + precedent_ready
        R->>S: trigger rule? (GRI / aggregate impact)
        S->>L: append stress run
        R->>A: recompute weights (tilt, caps, deadband)
        A->>L: append rebalance (auto or approved)
        L-->>T: hash chain verified
    end
```

### PRECEDENT: the memory

```mermaid
flowchart TD
    A["New signal at time t<br/>embedding + event type"] --> B["Analog search<br/>cosine similarity<br/>only events before t"]
    B --> C["Forward paths<br/>SPY and sector returns<br/>day 0 to +20"]
    C --> D["Shrinkage<br/>w = n / (n + 5)"]
    D --> E["Median and P10-P90<br/>fan chart"]
    D --> F["Percentile to 1-10<br/>shock severity"]
    F --> G["Calibrated shock vector<br/>per risk factor"]
    G --> H["Stress Lab"]
```

### Stress Lab and Adaptive Index

```mermaid
flowchart LR
    subgraph Stress Lab
        SC["Scenario library<br/>8 historical events<br/>or manual sliders"] --> RV["Full revaluation<br/>equity · bonds · loans · derivatives"]
        RV --> M["VaR / ES before and after"]
        RV --> SH["Shapley attribution<br/>factor · sector · country"]
        RV --> RS["Reverse stress<br/>worst-shock solver"]
        RV --> TR["Trigger rules<br/>and alerts"]
    end
    subgraph Adaptive Index
        Z["Decayed signal z-score"] --> W["Tilt<br/>w = bench · exp(κ·z)"]
        W --> C["Caps 15% · floor 2%<br/>deadband · turnover ≤ 5%"]
        C --> Q{"Mode"}
        Q -->|Auto| AP["Apply"]
        Q -->|PM approval| PM["Approve or reject"]
    end
    TR --> LG[("Hash-chained ledger")]
    AP --> LG
    PM --> LG
```

### Tamper-evident audit ledger

```mermaid
flowchart LR
    E1["entry n-2<br/>actor · action · ts<br/>hash a3f1…"] --> E2["entry n-1<br/>prev = a3f1…<br/>hash 5be8…"] --> E3["entry n<br/>prev = 5be8…<br/>hash c9d0…"]
    E3 -.->|"GET /api/audit/verify<br/>recompute every hash"| OK{{"Chain intact"}}
```

### Tech stack

| Layer | Choices |
|---|---|
| Backend | Python 3.11, FastAPI, asyncpg, APScheduler, Redis Streams, PostgreSQL 16 + pgvector |
| ML / NLP | PyTorch, Hugging Face Transformers (FinBERT zero-shot sentiment), sentence-transformers (MiniLM), scikit-learn / LightGBM, Captum |
| Quant | NumPy / SciPy: full revaluation, VaR / ES, Shapley attribution, gradient-based worst-shock solver |
| Frontend | React 19, TanStack Start / Router / Query, Tailwind 4, Recharts, Framer Motion, GSAP, three.js |
| Ops | Docker Compose (db, redis, api, ingest, serve, scheduler, ml), Makefile targets for every stage |

## 3. Dataset Used

All data is **public or synthetic**. No proprietary or client data is used.

| Data | Source | Used for |
|---|---|---|
| News events and themes | GDELT 2.0 GKG, publisher RSS | live and replayed signals |
| Company events | SEC EDGAR 8-K filings (15 stocks) | impact model (5,825 filings labelled with real abnormal returns) |
| Social | Bluesky Jetstream, Reddit (X/Twitter has no free read access, so it is not used live) | live signals |
| Prices and macro | Yahoo Finance (yfinance), FRED (rates, spreads, VIX) | PRECEDENT forward paths, index, stress factors |
| Labels | hand-labelled headlines: `data/labeling/gold_labels.csv`, held-out `test_labels.csv` | relevance gate, sentiment, event metrics |
| Wholesale banking book | **synthetic**, generated by code (109 holdings: loans, bonds, derivatives), labelled `SYNTHETIC` in the API | Stress Lab, exposure |
| Replay episodes | real archived periods, `data/replay/episodes.yaml` | demo without live feeds |

Assumptions (illustrative rating-migration matrix, LGD 45% loans / 60% bonds, tilt parameters, risk-index definition) are listed in [`docs/API.md`](docs/API.md#assumptions).
The CSV/JSON used to run the prototype lives in [`data/`](data/).

## 4. Quickstart & Installation

Runtime: **Python 3.11**, **Node 20+**, Docker (PostgreSQL 16 + pgvector, Redis 7) on Linux / macOS / WSL.

```bash
git clone https://github.com/chaitenyachand/IGDTUW-Chaitenya-Chand-Hackathon.git
cd IGDTUW-Chaitenya-Chand-Hackathon
cp .env.example .env          # set SEC_USER_AGENT and FRED_API_KEY (free); Reddit keys optional
make up                       # Postgres + Redis + API + ingest (Docker Compose)
make bootstrap                # migrate, seed, prices, FRED, EDGAR, train impact model,
                              # PRECEDENT library, synthetic book
make train-final              # freeze the production NLP models -> models/hybrid_v1.joblib
make serve scheduler          # scoring worker (live + replay) and the periodic jobs
curl -s localhost:8000/api/health        # {"data":{"status":"ok", ...}}
```

Terminal (frontend):

```bash
cd frontend
cp .env.example .env.local    # VITE_API_BASE_URL=http://localhost:8000
                              # VITE_WS_URL=ws://localhost:8000/ws/signals
npm install
npm run dev                   # landing page: http://localhost:8080   terminal: /app
npm run build                 # production build
```

Handy extras:

```bash
make replay-fetch EPISODE=svb-2023-03   # real archived episode (GDELT GKG) for a keyless demo
make test                               # 139 automated tests
make audit-verify                       # recompute the audit hash chain
make eval-test                          # ONE-SHOT held-out evaluation of the frozen pipeline
```

Set `API_TOKEN` in `.env` (and `VITE_API_TOKEN` in `frontend/.env.local`) to protect write endpoints.

## 5. Key Results & Domain Impact

### Measured, not claimed

| Component | Metric | SENTINEL | Naive baseline |
|---|---|---|---|
| Relevance gate (held-out n = 150, 29 relevant) | AUC | **0.78** | 0.56 (rules only) |
| Relevance gate | F1 (95% CI 0.22 to 0.54) | 0.39 | 0.34 |
| Sentiment (n = 29 relevant) | Accuracy | **55.2%** | 41.4% (majority class) |
| Event classifier | Macro-F1 | 0.32 (learned) | 0.47 (rules keep the final override) |
| Impact model (5,825 8-K events) | MAE | 0.0187 | 0.0195 (Spearman 0.33) |
| Adaptive Index (30-day demo backfill, synthetic prices) | Turnover | **15.0%** | 58.5% (naive rebalance) |
| Stress Lab (109 holdings) | Full run | **about 0.2 s** | n/a |

The held-out set is small, so intervals are wide; the event classifier is honestly weaker than the rules, which is why rules keep the override.
Raw metrics: [`data/models/`](data/models/).

### Why it matters

- **Credit and ratings surveillance:** evidence-backed early warning on issuers and sectors, with the closest past events attached.
- **Index and portfolio management:** signal-tilted weights inside caps, a lower-turnover rebalance, optional PM approval.
- **Risk and compliance:** stress runs that can be replayed, attributed and verified from a tamper-evident ledger.

Outputs are risk analytics for demonstration, not investment advice.

## 6. The terminal, view by view

The landing page and the nine-view terminal run on the same API. Screens below are captured from the running app on seeded **synthetic** demo data.

<table>
<tr>
<td width="50%"><img src="docs/screenshots/landing-precedent.jpg" alt="Landing: every event has a precedent"><br><sub><b>Landing</b>: every event has a precedent</sub></td>
<td width="50%"><img src="docs/screenshots/landing-impact.jpg" alt="Landing: see the impact before it lands"><br><sub><b>Landing</b>: see the impact before it lands</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/overview.jpg" alt="Command Center"><br><sub><b>Command Center</b>: global risk index, live signal stream, event heatmap, trigger rules</sub></td>
<td><img src="docs/screenshots/signals.jpg" alt="Signals"><br><sub><b>Signals</b>: drawer with sentiment, event class, integrity and book impact</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/precedent.jpg" alt="PRECEDENT"><br><sub><b>PRECEDENT</b>: analogs, fan chart, calibrated shock vector</sub></td>
<td><img src="docs/screenshots/stress-lab.jpg" alt="Stress Lab"><br><sub><b>Stress Lab</b>: scenario run, VaR / ES, attribution, reverse stress</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/adaptive-index.jpg" alt="Adaptive Index"><br><sub><b>Adaptive Index</b>: weights, turnover, approval mode, backtest</sub></td>
<td><img src="docs/screenshots/exposure.jpg" alt="Exposure"><br><sub><b>Exposure</b>: world map, contagion graph and sector treemap</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/portfolio.jpg" alt="Portfolio"><br><sub><b>Portfolio</b>: 109 synthetic holdings, $10.54B</sub></td>
<td><img src="docs/screenshots/model.jpg" alt="Model Lab"><br><sub><b>Model Lab</b>: model card, metrics and known limitations</sub></td>
</tr>
<tr>
<td colspan="2"><img src="docs/screenshots/audit.jpg" alt="Audit ledger"><br><sub><b>Audit</b>: hash-chained ledger, chain verified in one click</sub></td>
</tr>
</table>

## 7. Slide deck

Seven slides following the hackathon outline: [`docs/presentation.pdf`](docs/presentation.pdf) · editable [`docs/presentation.pptx`](docs/presentation.pptx).

| | | |
|---|---|---|
| ![Slide 1](docs/deck/slide-1.jpg) | ![Slide 2](docs/deck/slide-2.jpg) | ![Slide 3](docs/deck/slide-3.jpg) |
| ![Slide 4](docs/deck/slide-4.jpg) | ![Slide 5](docs/deck/slide-5.jpg) | ![Slide 6](docs/deck/slide-6.jpg) |
| ![Slide 7](docs/deck/slide-7.jpg) | | |

## 8. Repository layout

```text
IGDTUW-Chaitenya-Chand-Hackathon/
├── README.md
├── LICENSE                      MIT
├── requirements.txt · requirements-ml.txt
├── docker-compose.yml · Dockerfile · Dockerfile.ml · Makefile · .env.example
├── src/sentinel/
│   ├── ingest/                  GDELT, RSS, EDGAR, social, FRED, prices connectors
│   ├── nlp/ · ml/ · model/      relevance gate, event classifier, FinBERT sentiment, serving
│   ├── precedent/               point-in-time analog engine and event library
│   ├── impact/                  8-K abnormal-return impact model
│   ├── stress/ · portfolio/     full revaluation, VaR/ES, Shapley, reverse stress, synthetic book
│   ├── index/ · risk/           Adaptive Index and Global Risk Index
│   ├── audit/                   SHA-256 hash-chained ledger
│   ├── api/                     FastAPI REST + WebSocket
│   └── jobs/ · demo/ · cli.py   scheduler, replay episodes, make targets
├── frontend/                    React 19 + TanStack landing page and terminal
├── db/                          migrations
├── data/                        labels, metrics, replay episodes
├── models/                      frozen model artefacts
├── tests/                       139 automated tests
└── docs/
    ├── presentation.pdf         5-7 slide deck (submission copy)
    ├── presentation.pptx        editable deck
    ├── architecture.png         high-resolution architecture diagram
    ├── API.md                   endpoint reference and assumptions
    ├── diagrams/                diagram sources and renders
    └── screenshots/ · deck/     images used in this README
```

## 9. API

REST under `/api` and a WebSocket at `/ws/signals`. Success is `{"data": ..., "meta": {"source": "live|replay|backfill|synthetic", "asOf": ...}}`.

| Area | Endpoints |
|---|---|
| Signals | `GET /signals`, `GET /signals/{id}`, `GET /documents` |
| PRECEDENT | `GET /precedent/{signalId}` |
| Risk | `GET /risk-index`, `GET /alerts` |
| Index | `GET /index/constituents\|weights\|rebalances\|performance\|config`, `POST /index/recompute`, approve / reject |
| Portfolio / Stress | `GET /portfolio`, `GET /portfolio/exposure`, `POST /stress/run`, `GET /stress/runs/{id}/brief` (PDF), rules, reverse stress |
| Model / Audit | `GET /model/metrics`, `GET /audit`, `GET /audit/verify` |
| Demo / Health | `POST /demo/inject\|reset`, `GET /health` |

Full contract and assumptions: [`docs/API.md`](docs/API.md).

## 10. Tests

```bash
make test        # 139 automated tests: NLP, PRECEDENT, stress maths, index, audit, API and WebSocket contract
```

Tests use clearly labelled synthetic fixtures (`tests/*_fixtures.py`) so they run without network access.
`tests/test_frontend_contract.py` checks every endpoint and WebSocket message against the frontend's TypeScript types.

## 11. Limitations & responsible use

- The gold label set is small (150 held-out headlines, 29 relevant): relevance F1 95% CI 0.22 to 0.54. Directional, not definitive.
- The learned event classifier (macro-F1 0.32) trails the rules (0.47), so rules keep the final say.
- The impact model's lift over baseline is modest (MAE 0.0187 vs 0.0195).
- The wholesale book and its rating-migration matrix are synthetic by design.
- Live connectors (Yahoo, FRED, SEC, GDELT) need network access and keys; the demo also runs on replayed archived episodes.
- Outputs are risk analytics for demonstration, **not investment advice**.
- **AI usage:** built with AI assistance (Claude). Data choices, validation and all claims are the author's responsibility; every number above comes from stored data or the held-out evaluation, and demo data is labelled synthetic.

## 12. License

[MIT](LICENSE) © 2026 Chaitenya Chand
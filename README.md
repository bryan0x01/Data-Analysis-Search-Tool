## Note on Data Privacy
This project was originally developed in the context of a data operations internship.
To respect data privacy and confidentiality, all datasets included in this repository
are synthetic, and certain implementation details have been generalized.

# User Search
Web App that combines **pandas + SQL (SQLite) + FastAPI**:

- **pandas**: ingest + normalization + quality/summary analytics
- **SQLite (SQL)**: store cleaned records + fast searching
- **FastAPI**: API endpoints consumed by the frontend

## Folder structure

```
campus_data_search/
  app.py
  web_app.py
  my_exports/  
  app.db
  static/
    index.html
    style.css
    app.js
```

## Run

### 1) Create venv + install deps
```bash
python3 -m venv .venv
source .venv/bin/activate   # Mac/Linux
# .venv\Scripts\activate  # Windows

pip install fastapi uvicorn pandas openpyxl
```

### 2) Start the server
```bash
uvicorn web_app:app --reload
```

Open: http://127.0.0.1:8000

## Data reload
Drop new files into `my_exports/` and click **Reload Data** (or call `GET /api/reload`).

## Endpoints
- `GET /api/search?q=...` -> list results
- `GET /api/record?record_id=...` -> details + raw JSON
- `GET /api/insights` -> pandas metrics
- `GET /api/reload` -> re-ingest from my_exports into SQLite

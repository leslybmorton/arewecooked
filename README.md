# Are We Cooked? 🌍 — Streamlit

A Streamlit dashboard for tracking global systemic risk.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository.
2. Upload `app.py` and `requirements.txt`.
3. Go to Streamlit Community Cloud.
4. Click **Create app**.
5. Select your repository and set the main file path to `app.py`.
6. Deploy.

## Updating the daily report

For now, all dashboard data is near the top of `app.py`:
- `AS_OF`
- `OVERALL_SCORE`
- `OVERALL_TREND`
- `categories`
- `history`
- `changes`
- `pathways`

That makes the first hosted version easy to edit without setting up a database.

A good next version would move the daily data to a separate JSON/CSV file or Google Sheet and add automatic daily history.

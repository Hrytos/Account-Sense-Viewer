# Account Sense Viewer

Web app for viewing account/site analysis data from Supabase, with GPT-4o mini summaries.

## Quick Start

```bash
git clone <your-repo-url>
cd account_sense_viewer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with your credentials, then run:

```bash
source venv/bin/activate
streamlit run app/streamlit_app.py
```

## Required Environment Variables

Set these in `.env`:

- `supabase_url`
- `supabase_key`
- `OPENAI_API_KEY`

## Features

- Account/site data pulled from Supabase (read-only)
- AI-generated account summary (GPT-4o mini)
- AI-generated company overview (GPT-4o mini)
- AI-generated assertion narrative (GPT-4o mini)
- Assertions table with wrapped in-cell text for readability

## Project Structure

```
account_sense_viewer/
├── .env.example
├── .gitignore
├── README.md
├── flow.md
├── requirements.txt
└── app/
    ├── streamlit_app.py
    ├── data_fetcher.py
    ├── ai_summarizer.py
    ├── about_account.py
    └── assertion_summary.py
```

## Notes

- Python 3.10+ recommended
- All DB operations are read-only

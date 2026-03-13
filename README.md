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

Fill `.env` with your credentials (including `username` and `password` for login), then run:

```bash
source venv/bin/activate
streamlit run app/streamlit_app.py
```

**Login credentials are set in your `.env` file.** The login form will appear automatically when you first access the app.

## Required Environment Variables

Set these in `.env`:

- `supabase_url` - Your Supabase project URL
- `supabase_key` - Your Supabase service role key
- `OPENAI_API_KEY` - Your OpenAI API key
- `username` - Login username (default: admin)
- `password` - Login password

## Features

- Simple login authentication (username/password)
- Account/site data pulled from Supabase (read-only)
- AI-generated account summary (GPT-4o mini)
- AI-generated company overview (GPT-4o mini)
- AI-generated assertion narrative (GPT-4o mini)
- Assertions table with wrapped in-cell text for readability
- Metric cards for key information
- Clean, modern UI with section headers

## Project Structure

```
account_sense_viewer/
├── .env.example
├── .gitignore
├── README.md
├── flow.md
├── requirements.txt
├── app/
│   └── streamlit_app.py      # Main application (with embedded login)
└── src/
    ├── core/
    │   └── clients.py         # Supabase client
    └── services/
        ├── data_fetcher.py    # Data fetching logic
        └── ai_summarizer.py   # AI summary generation
```

## Notes

- Python 3.10+ recommended
- All DB operations are read-only

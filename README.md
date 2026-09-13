# PrimeFit AI
AI-powered fitness + budget-based nutrition platform built with Python, Streamlit, Supabase, Groq and Plotly.

## Streamlit Secrets
In Streamlit Cloud → App → Settings → Secrets:

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_PUBLISHABLE_KEY"
GROQ_API_KEY = "YOUR_GROQ_API_KEY"
```

Never commit `.streamlit/secrets.toml` or a Supabase service-role/secret key.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important
The app expects the Supabase tables from the PrimeFit AI database schema already created in the project. RLS must permit the intended user operations. Admin roles are controlled by `admin_roles`.

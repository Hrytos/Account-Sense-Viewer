"""
Core Clients Module
Centralized initialization for Supabase and OpenAI clients.
"""

import os
import httpx
from supabase import create_client, Client
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables if .env exists (mainly for local development)
# Vercel provides environment variables directly.
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

def get_supabase_client() -> Client:
    """
    Initialize and return a Supabase client.
    """
    url = os.getenv('SUPABASE_URL') or os.getenv('supabase_url')
    key = os.getenv('SUPABASE_KEY') or os.getenv('supabase_key')
    
    if not url or not key:
        raise ValueError("Supabase credentials not found in environment.")
    
    return create_client(url, key)

def get_openai_client() -> OpenAI:
    """
    Initialize and return an OpenAI client.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found in environment.")
    
    # Use an explicit HTTP client to avoid potential proxy issues in serverless environments
    return OpenAI(api_key=api_key, http_client=httpx.Client())

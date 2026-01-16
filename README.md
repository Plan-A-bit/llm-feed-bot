# LLM Feed Bot

Offline knowledge ingestion for local LLMs. Fetches trusted docs (man, RFCs, GPG) into ~/.local/share/llmfeed/.  
AI ops (summarize/classify) only affect files modified in the last 5 minutes — to avoid RAM/cache overload.

Start LLM server on localhost:8080, then run:
python3 llm_bot.py

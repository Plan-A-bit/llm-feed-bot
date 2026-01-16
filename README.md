# LLM Feed Bot

Offline knowledge ingestion for local LLMs. Fetches trusted docs (man, RFCs, GPG) into ~/.local/share/llmfeed/.  
AI ops (summarize/classify) only affect files modified in the last 5 minutes — to avoid RAM/cache overload.

Start LLM server on localhost:8080, then run:
python3 llm_bot.py in a 2nd shell.


The Man page tab has a fetch button just press once i's a background proces that takes a minute or 3.

## How to Install & Use

bash
git clone https://github.com/Plan-A-bit/llm-feed-bot.git
cd llm-feed-bot
# Fedora/RHEL:
sudo dnf install python3-pyqt6 python3-requests python3-beautifulsoup4
# Debian/Ubuntu:
sudo apt install python3-pyqt6 python3-requests python3-bs4
./server -m qwen-2.5-coder.Q4_K_M.gguf --port 8080  # start LLM server
python3 llm_bot.py  # run the bot


workflow:
1. In Custom URL tab / Command :put in a valid URL then click add > then click Scrape
    ↓

2. In Man Pages Tab Fetch → Save as .txt in ~/.local/share/llmfeed/ 
    ↓
(Within 5 min?) → Yes → AI ops (LLM @ localhost:8080)
                → No  → Skipped (to save RAM/cache)

3. Summarize tab > click the button there is no progress visible as it runs on the background.

4. Extract code, fast background process

5. Build Index, fast background process

6. Classify it, also 1 click runs in baclground as the previous just be patient don't click twice it will appear confirmed.

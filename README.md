# LLM Feed Bot

Offline knowledge ingestion for local LLMs. Fetches trusted docs (man, RFCs, GPG) into ~/.local/share/llmfeed/.  
AI ops (summarize/classify) only affect files modified in the last 5 minutes — to avoid RAM/cache overload.

Start LLM server on localhost:8080, then run:
python3 llm_bot.py in a 2nd shell.


The Man page tab has a fetch button just press once it's a background proces that takes a minute or 3.

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




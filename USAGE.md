# Workflow: The 5-Minute Rule

1. Fetch content → saved as .txt in ~/.local/share/llmfeed/
2. Within 5 minutes, use AI tabs (Summarize, Classify, etc.)
3. After 5 minutes, old files are skipped automatically.

Example: Paste https://man7.org/linux/man-pages/man7/capabilities.7.html → Scrape → Summarize within 5 min.


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

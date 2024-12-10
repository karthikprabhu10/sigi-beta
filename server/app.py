from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
import requests
from concurrent.futures import ThreadPoolExecutor
from transformers import T5Tokenizer, T5ForConditionalGeneration
import torch
import time
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# Load T5-small model for summarization
tokenizer = T5Tokenizer.from_pretrained("t5-small")
model = T5ForConditionalGeneration.from_pretrained("t5-small")

# Function to fetch results from Google
def fetch_top_sites(query):
    excluded_domains = ["maps.google.com"]
    headers = {'User-Agent': 'Mozilla/5.0'}
    google_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    try:
        response = requests.get(google_url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract top result links
        links = []
        for result in soup.find_all('a', href=True):
            href = result['href']
            if href.startswith("/url?q="):
                link = href.split("/url?q=")[1].split("&")[0]
                if link.startswith('http') and all(domain not in link for domain in excluded_domains):
                    links.append(link)

        # Deduplicate domains
        seen_domains = set()
        unique_links = []
        for link in links:
            domain = urlparse(link).netloc
            if domain not in seen_domains:
                seen_domains.add(domain)
                unique_links.append(link)

        return unique_links[:5]  # Limit to 5 unique links
    except Exception as e:
        print(f"Error fetching Google results: {e}")
        return []

# Function to fetch content from a single URL
def fetch_content_from_url(link):
    try:
        start_time = time.time()
        page = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        fetch_time = time.time() - start_time

        soup = BeautifulSoup(page.text, "html.parser")
        paragraphs = soup.find_all("p")
        content = " ".join([p.text for p in paragraphs[:15]])  # Collect first 3 paragraphs

        scrape_time = time.time() - start_time - fetch_time
        return content.strip(), fetch_time, scrape_time
    except Exception as e:
        print(f"Error fetching content from {link}: {e}")
        return "", 0, 0

# Function to fetch content in parallel
def fetch_content_in_parallel(links):
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_content_from_url, links))

    contents = []
    fetch_times = []
    scrape_times = []

    for content, fetch_time, scrape_time in results:
        if content:  # Only include valid content
            contents.append(content)
        fetch_times.append(fetch_time)
        scrape_times.append(scrape_time)

    return " ".join(contents), sum(fetch_times), sum(scrape_times)

# Function to summarize content using T5-small
def summarize_content(content):
    try:
        start_time = time.time()
        inputs = tokenizer.encode("summarize: " + content, return_tensors="pt", max_length=5120, truncation=True)
        summary_ids = model.generate(inputs, max_length=4000, min_length=100, length_penalty=2.0, num_beams=4, early_stopping=True)
        summarize_time = time.time() - start_time
        return tokenizer.decode(summary_ids[0], skip_special_tokens=True), summarize_time
    except Exception as e:
        print(f"Error during summarization: {e}")
        return "Error summarizing content.", 0

@app.route("/")
def home():
    return "Flask server is running. Use the /search endpoint with a query."

@app.route("/search", methods=["GET"])
def search():
    query = "about " + request.args.get("q", "")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    links = fetch_top_sites(query)
    if not links:
        return jsonify({"query": query, "links": [], "summary": "No links found for the query."})

    content, fetch_time, scrape_time = fetch_content_in_parallel(links)
    if not content:
        return jsonify({"query": query, "links": links, "summary": "No meaningful content found."})

    summary, summarize_time = summarize_content(content)
    return jsonify({
        "query": query,
        "links": links,
        "summary": summary,
        "timing": {
            "fetch_time": fetch_time,
            "scrape_time": scrape_time,
            "summarize_time": summarize_time
        }
    })

if __name__ == "__main__":
    app.run(debug=True)

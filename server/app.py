from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
import requests
from concurrent.futures import ThreadPoolExecutor
import time
from urllib.parse import urlparse, unquote
from transformers import pipeline

app = Flask(__name__)
CORS(app)

# Load a text generation model capable of dynamic inference
text_generator = pipeline("text-generation", model="distilgpt2")

def fetch_top_sites(query):
    excluded_domains = {"maps.google.com", "www.google.com", "accounts.google.com", "support.google.com"}
    headers = {'User-Agent': 'Mozilla/5.0'}
    google_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    try:
        response = requests.get(google_url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        links = []
        for result in soup.find_all('a', href=True):
            href = result['href']
            if href.startswith("/url?q="):
                link = href.split("/url?q=")[1].split("&")[0]
                link = unquote(link)
                if link.startswith('http'):
                    domain = urlparse(link).netloc
                    if domain not in excluded_domains:
                        links.append(link)

        seen_domains = set()
        unique_links = []
        for link in links:
            domain = urlparse(link).netloc
            if domain not in seen_domains:
                seen_domains.add(domain)
                unique_links.append(link)

        return unique_links[:5]
    except Exception as e:
        print(f"Error fetching Google results: {e}")
        return []

def fetch_content_from_url(link):
    try:
        page = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
        soup = BeautifulSoup(page.text, "html.parser")
        paragraphs = soup.find_all("p")
        content = " ".join([p.text for p in paragraphs[:3]])
        return content
    except Exception as e:
        print(f"Error fetching content from {link}: {e}")
        return ""

def fetch_content_in_parallel(links):
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_content_from_url, links))
    return " ".join(results)

def generate_structured_response(content, query):
    prompt = f"""
    Analyze the following content and generate a structured summary based on the query type.
    Query: {query}
    Content: {content}
    
    The summary should include key points in a formatted structure with emojis. Examples of possible structures:
    - For a person: 📝 Full Name, 🎂 Date of Birth, 📍 Place, 🏛️ Political Party.
    - For a company: 📅 Founded, 🚗 Products, 🧑‍🤝‍🧑 Key People.
    - For an event: 🗓️ Date, 📍 Location, 📜 Details.
    Generate points dynamically based on the content and available information.
    """

    response = text_generator(prompt, max_length=50000, num_return_sequences=1)
    return response[0]["generated_text"]

@app.route("/")
def home():
    return "Flask server is running. Use the /search endpoint with a query."

@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    links = fetch_top_sites(query)
    if not links:
        return jsonify({"query": query, "links": [], "summary": "No links found for the query."})

    combined_content = fetch_content_in_parallel(links)
    if not combined_content.strip():
        return jsonify({"query": query, "links": links, "summary": "No content available to summarize."})

    summary = generate_structured_response(combined_content, query)
    return jsonify({
        "query": query,
        "links": links,
        "summary": summary
    })

if __name__ == "__main__":
    app.run(debug=True)

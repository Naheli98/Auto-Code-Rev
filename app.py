import os
import hmac
import hashlib
import requests  # To talk to GitHub
from flask import Flask, request, jsonify
from dotenv import load_dotenv  # To read your .env file
from openai import OpenAI  # To talk to the AI brain

# 1. Load the secrets from your .env file
load_dotenv()
PASSWORD_ = "ASDFASJLDFLAKSJDF_ASDHLKJA"
# 2. Assign secrets to variables for easy use
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
GITHUB_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")

# 3. Initialize the AI Brain (OpenAI) and the Web Server (Flask)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = Flask(__name__)

def verify_signature(payload_body, signature_header):
    """Checks if the secret key from GitHub matches our own."""
    if not signature_header:
        return False
    
    # Re-calculate the signature using our secret and the message body
    hash_object = hmac.new(WEBHOOK_SECRET.encode('utf-8'), 
                           msg=payload_body, 
                           digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    # compare_digest is a secure way to compare two secret strings
    return hmac.compare_digest(expected_signature, signature_header)

def process_review(pr_data):
    """The main logic: Fetch code -> Ask AI -> Post Review."""
    
    # 1. Get important PR details
    pr_number = pr_data['number']
    repo_full_name = pr_data['base']['repo']['full_name']
    diff_url = pr_data['diff_url']

    # 2. Fetch the actual code changes (the "diff")
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3.diff' # We want raw text diff
    }
    diff_response = requests.get(diff_url, headers=headers)
    code_diff = diff_response.text

    # 3. Ask the AI Brain for a review
    system_prompt = "You are a Senior Software Engineer. Review this code diff for bugs and security risks. Be concise."
    ai_response = client.chat.completions.create(
        model="gpt-4o", # Or gpt-4o-mini for speed/lower cost
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Review this code change:\n\n{code_diff}"}
        ]
    )
    review_text = ai_response.choices[0].message.content

    # 4. Post the review as a comment on GitHub
    comment_url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
    comment_payload = {"body": f"### 🤖 R.E.V. Bot Review\n\n{review_text}"}
    
    requests.post(comment_url, json=comment_payload, headers=headers)
    print(f"✅ Review posted for PR #{pr_number}!")

@app.route('/webhook', methods=['POST'])

def github_webhook():
    # A. Check security signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        return "Unauthorized", 401

    # B. Get the message data
    event_data = request.json
    event_type = request.headers.get('X-GitHub-Event')

    # C. Only act if a new Pull Request is opened
    if event_type == 'pull_request' and event_data.get('action') == 'opened':
        print("🚀 New PR detected! Starting review...")
        process_review(event_data['pull_request'])
        
    return "OK", 200

@app.route('/favicon.ico')
def favicon():
    return '', 204  # 204 means "No Content" - it tells the browser "I hear you, but I have nothing for you."

@app.route('/')
def home():
    return "<h1>R.E.V. Bot is Online!</h1><p>Waiting for GitHub webhooks...</p>", 200

if __name__ == '__main__':
    # Running on port 8000 (remember to point ngrok to this port!)
    app.run(port=8000, debug=True)

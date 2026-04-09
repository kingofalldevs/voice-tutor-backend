import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Enable CORS for all origins in development
CORS(app)

# Ensure the Groq API key is set
groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key) if groq_api_key else None

SYSTEM_PROMPT = """You are a helpful voice assistant. Keep responses concise and conversational — ideally 1-3 sentences. Avoid markdown, bullet points, or lists since your responses will be read aloud."""

@app.route('/chat', methods=['POST'])
def chat():
    if not client:
        return jsonify({"error": "Groq API key not configured. Please set GROQ_API_KEY."}), 500
        
    data = request.json
    if not data or 'message' not in data:
        return jsonify({"error": "No message provided."}), 400

    user_message = data['message']
    history = data.get('history', [])
    
    print(f"--- New Message Received ---\nUser: {user_message}")

    # Construct the messages array for Groq
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add history (ensure the history items only contain role and content)
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        if role in ["user", "assistant"] and content:
            messages.append({"role": role, "content": content})
        
    # Append the new user message
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant", # Using the faster model for voice interaction
            messages=messages,
            max_tokens=300
        )
        reply = response.choices[0].message.content
        print(f"AI Reply: {reply}")
        return jsonify({"reply": reply})
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True, threaded=True)

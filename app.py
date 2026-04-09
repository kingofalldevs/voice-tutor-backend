from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
import os
import json

load_dotenv()

app = Flask(__name__)
CORS(app)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are an ultra-fast voice assistant. 
Respond in 1-2 VERY short sentences. 
No markdown. No lists. No emojis. 
Be concise to minimize latency."""

@app.route('/chat', methods=['POST'])
def chat():
    if not client:
        return jsonify({"error": "No API key"}), 500
        
    data = request.json
    user_message = data.get('message', '')
    history = data.get('history', [])
    user_name = data.get('userName', 'Friend')

    # Personalized System Prompt for memory and context
    system_content = f"""You are a helpful voice tutor. The user's name is {user_name}.
    Use the conversation history to stay in context. 
    If the user previously mentioned something, remember it.
    Keep responses very short (1-2 sentences) and conversational.
    No markdown or emojis."""

    messages = [{"role": "system", "content": system_content}]
    
    # Filter and add history
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        if role and content:
            messages.append({"role": role, "content": content})
            
    # Add most recent message
    messages.append({"role": "user", "content": user_message})

    def generate():
        try:
            stream = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                max_tokens=200,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"Error: {str(e)}"

    return Response(stream_with_context(generate()), mimetype='text/plain')

if __name__ == '__main__':
    app.run(port=5000, debug=True, threaded=True)

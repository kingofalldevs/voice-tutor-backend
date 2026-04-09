from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
CORS(app)

groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key) if groq_api_key else None


def build_system_prompt(user_name: str) -> str:
    return f"""You are a warm, patient, and encouraging AI tutor named Nova, having a spoken conversation with a student named {user_name}.

Your teaching behavior:
- At the very start of a session (no prior history), greet {user_name} by name and ask what they would like to learn today
- Teach one concept at a time — never overwhelm the student with too much at once
- After every explanation, ask a single follow-up question to check the student's understanding
- If the student answers correctly, praise them briefly and naturally advance to the next concept
- If the student answers incorrectly, gently correct them and re-explain using a different analogy or example
- If the student seems confused, simplify your language and try a completely different approach
- Always build on what was discussed earlier in the conversation — never repeat what has already been understood
- Adapt your vocabulary and complexity based on how the student responds

Your speaking style (critical — responses are read aloud):
- Keep every response to 2-3 sentences maximum
- Never use bullet points, numbered lists, headers, or any markdown
- Never use emojis or special characters
- Speak naturally and conversationally, as a real teacher would in person
- Be warm and encouraging — the student should feel safe making mistakes"""


@app.route("/chat", methods=["POST"])
def chat():
    if not client:
        return jsonify({"error": "GROQ_API_KEY is not set in your .env file"}), 500

    data = request.json
    if not data or "message" not in data:
        return jsonify({"error": "Request must include a message field"}), 400

    user_message = data["message"]
    history = data.get("history", [])
    user_name = data.get("userName", "Student")

    # Build messages array
    messages = [{"role": "system", "content": build_system_prompt(user_name)}]

    # Append validated history (last 20 messages for full session context)
    for msg in history[-20:]:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content and content.strip():
            messages.append({"role": role, "content": content.strip()})

    # Append the new user message
    messages.append({"role": "user", "content": user_message})

    def generate():
        try:
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            print(f"Groq API error: {e}")
            yield "I encountered an error. Please try again."

    return Response(stream_with_context(generate()), mimetype="text/plain")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "groq_configured": client is not None
    })


if __name__ == "__main__":
    app.run(port=5000, debug=True, threaded=True)
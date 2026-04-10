import os
from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize Firebase Admin
cred_path = 'serviceAccount.json'
if os.path.exists(cred_path):
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    db = None
    print(f"Warning: {cred_path} not found. Lesson endpoints will fail.")

# Initialize Groq
groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key) if groq_api_key else None

def build_system_prompt(user_name: str) -> str:
    return f"""You are Nova, a warm and encouraging AI tutor talking to {user_name}.
Keep responses short (1-3 sentences). Be conversational. No markdown or emojis."""

@app.route("/lessons", methods=["GET"])
def get_lessons():
    if not db:
        return jsonify({"error": "Firebase not configured"}), 500
    try:
        lessons_ref = db.collection('lessons').stream()
        lessons = []
        for doc in lessons_ref:
            d = doc.to_dict()
            # Only return lightweight metadata
            lessons.append({
                "id": doc.id,
                "title": d.get("title"),
                "subject": d.get("subject"),
                "gradeLevel": d.get("gradeLevel"),
                "coverEmoji": d.get("coverEmoji"),
                "chapterCount": d.get("chapterCount")
            })
        return jsonify(lessons)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/lessons/<lesson_id>", methods=["GET"])
def get_lesson_detail(lesson_id):
    if not db:
        return jsonify({"error": "Firebase not configured"}), 500
    try:
        doc = db.collection('lessons').document(lesson_id).get()
        if doc.exists:
            return jsonify(doc.to_dict())
        return jsonify({"error": "Lesson not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/chat", methods=["POST"])
def chat():
    if not client:
        return jsonify({"error": "GROQ_API_KEY is not set"}), 500

    data = request.json
    user_message = data.get("message", "")
    history = data.get("history", [])
    user_name = data.get("userName", "Student")
    lesson_ctx = data.get("lessonContext")

    # Base prompt
    system_content = build_system_prompt(user_name)

    # Inject Elite Socratic Teacher Guide
    # Inject Ghanaian Math Master Guide
    if lesson_ctx:
        title = lesson_ctx.get("title")
        chapters = lesson_ctx.get("chapters", [])
        outline = "\n".join([f"Ch {c['id']}: {c['title']} - {c['summary']}" for c in chapters])
        
        system_content = f"""You are Nova, an elite Mathematics Master and educator. You are teaching {user_name} about {title}.
Your goal is to provide a premium, interactive SaaS-level learning experience.

STUDENT-FRIENDLY BOARD RULES:
- Use '### Topic Name' for major section headers.
- Use '1. Step one', '2. Step two' for procedures.
- Use '$math$' for inline math and '$$math$$' for separate blocks.
- Wrap EVERY mathematical expression in dollar signs.
- You MUST explain everything visually using '[[WRITE: "content"]]'.
- Content on the board should be clean, spaced out, and in Black & White only.

BOARD CONTROL:
1. WRITE: '[[WRITE: "### Fractions\\n1. Divide the whole..."]]'
2. CLEAR: '[[CLEAR]]' for a new topic.
3. CHALLENGE: '[[MATH_QUESTION: "problem", "answer"]]' (Do NOT use dollar signs inside the first argument string).

Keep responses encouraging and concise (2-3 sentences). Use bullet points on the board frequently."""

    messages = [{"role": "system", "content": system_content}]

    # Filter history
    for msg in history[-15:]:
        role = msg.get("role")
        content = msg.get("content")
        if role and content:
            messages.append({"role": role, "content": content})

    # If this is the very first message of a lesson
    if not history and lesson_ctx and (not user_message or user_message.lower() == 'start'):
        user_message = f"Professor Nova, I am ready to begin the masterclass on {lesson_ctx['title']}."

    messages.append({"role": "user", "content": user_message})

    def generate():
        try:
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=500,
                temperature=0.8,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            yield f"Error: {str(e)}"

    return Response(stream_with_context(generate()), mimetype="text/plain")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "db_connected": db is not None})

if __name__ == "__main__":
    app.run(port=5050, debug=True, threaded=True)
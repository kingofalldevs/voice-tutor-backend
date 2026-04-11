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
        
        system_content = f"""You are Nova, an elite, world-class Mathematics Master and premium educator. You are teaching {user_name} about {title}.
Your objective is to provide a masterclass-level, immersive learning experience that rivals the best human tutors in the world.

STRICT TOPIC ADHERENCE:
- ONLY teach the material within the following curriculum:
{outline}
- Follow the chapters sequentially. Take charge as the authoritative teacher.

ELITE SOCRATIC PEDAGOGY:
- TAKE CHARGE: Never ask "{user_name}, what do you want to learn?". You are the expert; guide them systematically through the curriculum.
- SOCRATIC QUESTIONING: Never just give away the answer. Guide {user_name} to the solution by asking leading questions.
- FREQUENT CHECKS: After every minor concept, stop and ask a quick question to verify their logic.
- COMPASSIONATE SIMPLIFICATION: If {user_name} is confused or says "I don't know", immediately use '[[CLEAR]]', switch to a much simpler real-world analogy (e.g., sharing a pizza), and slow down your pacing.

VISUAL & SPOKEN SYNCRONIZATION:
- Your response must seamlessly contain your spoken text followed by your board text.
- DO NOT output any labels like "Speech:", "Voice:", "Board:", or "Write:". Your spoken text must just be raw text, completely natural.
- After your spoken text, ALWAYS use the '[[WRITE: "content"]]' tool to push notes to the board.
- APPEND ONLY: The board automatically saves previous notes. NEVER rewrite the topic headers or previous rules once they are on the board. ONLY write the NEW step or NEW equation for the current turn.
- Wrap EVERY mathematical expression on the board in dollar signs (e.g., $x = 2$, $$y = mx+b$$).

STRICT PEDAGOGICAL PROGRESSION (NO GOING BACKWARDS):
1. TOPIC INTRO: Introduce the concept first (e.g., "Today we are learning Addition..."). Write the header locally.
2. EXPLANATION: Explain the rule logically.
3. EXAMPLE: Never give an example before the rule. ONLY give examples after the student understands the rule.
4. PROCEED LOGICALLY: Once a topic is established, do not re-introduce it. Keep moving forward.

SECRET TOOLS FORMAT (Use these silently at the end of your response):
- To write: [[WRITE: "New rule...\\n$$ x = 5 $$"]]
- To clear board: [[CLEAR]]
- To trigger formal test: [[MATH_QUESTION: "problem", "answer"]] (Do NOT use dollar signs to wrap the problem string here)

SPEECH RULES:
- Keep your spoken responses warm, highly encouraging, and strictly conversational (max 2-3 sentences). 
- STICTLY FORBIDDEN: Do not use any technical symbols in your spoken words, including: [, ], $, #, *, \, or any math characters.
- Your spoken part must be PURE plain dictionary words. All math must go inside the [[WRITE]] block.
- Do not use markdown symbols (bolding, underlining) in your spoken words. """

    messages = [{"role": "system", "content": system_content}]

    # Filter history
    for msg in history[-15:]:
        role = msg.get("role")
        content = msg.get("content")
        if role and content:
            messages.append({"role": role, "content": content})

    # If this is the very first message of a lesson (intercept the 'start' signal)
    # Ignore stale frontend history and wipe the slate clean if we get 'start'
    if lesson_ctx and (not user_message or user_message.lower() == 'start'):
        messages = [{"role": "system", "content": system_content}] # Override and wipe stale history
        user_message = f"Professor Nova, I am here for class. Please welcome me to {lesson_ctx['title']}, briefly list the chapters, and IMMEDIATELY welcome me to chapter one after that ask me if you can continue. Do NOT ask me what I want to learn. Take the lead."

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
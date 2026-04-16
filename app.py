import os
from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

import json

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://nova-tutor-ai.web.app", "http://localhost:5173"]}})

# Initialize Firebase Admin
def init_firebase():
    # Try environment variable first (for Render/Production)
    fb_service_account = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if fb_service_account:
        try:
            cred_dict = json.loads(fb_service_account)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            return firestore.client()
        except Exception as e:
            print(f"Error initializing Firebase from env: {e}")
    
    # Fallback to local file
    cred_path = 'serviceAccount.json'
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        return firestore.client()
    
    print(f"Warning: Firebase not configured. Lesson endpoints will fail.")
    return None

db = init_firebase()

# Initialize Groq
groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key) if groq_api_key else None

def build_system_prompt(user_name: str) -> str:
    return f"""You are Nova, a warm and encouraging AI tutor talking to {user_name}.
Keep responses short (1-3 sentences). Be conversational. No markdown or emojis."""

@app.route("/onboarding", methods=["POST"])
def onboarding():
    if not db:
        return jsonify({"error": "Firebase not configured"}), 500
    data = request.json
    uid = data.get("uid")
    if not uid:
        return jsonify({"error": "Missing uid"}), 400
    
    # Map country/grade to path_id
    country = data.get("country", "US")
    grade = data.get("grade", 6)
    path_id = f"{country.lower()}_grade_{grade}"
    
    user_data = {
        "name": data.get("name"),
        "age": data.get("age"),
        "country": country,
        "state": data.get("state"),
        "grade": grade,
        "learning_path_id": path_id,
        "updatedAt": firestore.SERVER_TIMESTAMP
    }
    
    db.collection('users').document(uid).set(user_data, merge=True)
    
    # Remove SERVER_TIMESTAMP before returning JSON (it's not serializable)
    response_data = {**user_data}
    response_data.pop('updatedAt', None)
    response_data['uid'] = uid
    
    return jsonify({"status": "success", "profile": response_data})

@app.route("/curriculum/<path_id>", methods=["GET"])
def get_curriculum(path_id):
    if not db:
        return jsonify({"error": "Firebase not configured"}), 500
    try:
        # Fetch all standards for this path
        # Note: Hierarchy is learning_paths/{id}/domains/{d}/clusters/{c}/standards/{s}
        # For simplicity, we can fetch all standards under this path across all domains
        standards = []
        print(f"DEBUG: Fetching curriculum for path_id={path_id}")
        domains_ref = db.collection('learning_paths').document(path_id).collection('domains').stream()
        
        found_any = False
        for d_doc in domains_ref:
            domain_name = d_doc.id
            found_any = True
            print(f"  Found Domain: {domain_name}")
            clusters_ref = d_doc.reference.collection('clusters').stream()
            for c_doc in clusters_ref:
                cluster_name = c_doc.id
                print(f"    Found Cluster: {cluster_name}")
                stds_ref = c_doc.reference.collection('standards').stream()
                for s_doc in stds_ref:
                    s_data = s_doc.to_dict()
                    print(f"      Found Standard: {s_doc.id}")
                    # Fetch skills
                    skills_ref = s_doc.reference.collection('skills').stream()
                    skills_list = []
                    for sk_doc in skills_ref:
                        sk_data = sk_doc.to_dict()
                        skills_list.append({
                            "id": sk_doc.id,
                            "title": sk_data.get("title"),
                            "difficulty": sk_data.get("difficulty")
                        })
                    
                    standards.append({
                        "id": s_doc.id,
                        "domain": domain_name,
                        "cluster": cluster_name,
                        "title": s_data.get("title"),
                        "description": s_data.get("description"),
                        "skills": skills_list
                    })
        
        if not found_any:
            print(f"  WARNING: No domains found for {path_id}")
        print(f"DEBUG: Returning {len(standards)} standards for {path_id}")
        
        return jsonify(standards)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/lessons", methods=["GET"])
def get_lessons():
    # Deprecated in favor of curriculum, but keeping for compatibility during migration
    if not db:
        return jsonify({"error": "Firebase not configured"}), 500
    try:
        lessons_ref = db.collection('lessons').stream()
        lessons = []
        for doc in lessons_ref:
            d = doc.to_dict()
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
        # Check standard format first
        # Format: path:domain:cluster:standard
        if ":" in lesson_id:
            parts = lesson_id.split(":")
            if len(parts) == 4:
                path, dom, clus, std = parts
                doc = db.collection('learning_paths').document(path) \
                        .collection('domains').document(dom) \
                        .collection('clusters').document(clus) \
                        .collection('standards').document(std).get()
                if doc.exists:
                    std_data = doc.to_dict()
                    # Fetch skills
                    skills_ref = doc.reference.collection('skills').stream()
                    std_data['skills'] = [s.to_dict() for s in skills_ref]
                    return jsonify(std_data)

        # Fallback to old lessons
        doc = db.collection('lessons').document(lesson_id).get()
        if doc.exists:
            return jsonify(doc.to_dict())
        return jsonify({"error": "Lesson not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/progress/<uid>", methods=["GET"])
def get_progress(uid):
    if not db:
        return jsonify({"error": "Firebase not configured"}), 500
    try:
        skills_ref = db.collection('user_progress').document(uid).collection('skills').stream()
        progress = {s.id: s.to_dict() for s in skills_ref}
        return jsonify(progress)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/chat", methods=["POST"])
def chat():
    if not client:
        return jsonify({"error": "GROQ_API_KEY is not set"}), 500

    data = request.json
    uid = data.get("uid")
    user_message = data.get("message", "")
    history = data.get("history", [])
    user_name = data.get("userName", "Student")
    
    # Curriculum Context
    lesson_ctx = data.get("lessonContext", {}) 
    current_skill_id = data.get("currentSkillId") or lesson_ctx.get("currentSkillId")
    
    # Ensure currentSkillId is extracted if sent inside lessonContext
    if not current_skill_id and lesson_ctx:
        current_skill_id = lesson_ctx.get("currentSkillId")
    
    # 1. Fetch User Profile
    user_profile = {}
    if uid and db:
        u_doc = db.collection('users').document(uid).get()
        if u_doc.exists:
            user_profile = u_doc.to_dict()

    # 2. Fetch/Init Mastery
    mastery = 0.0
    attempts = 0
    if uid and current_skill_id and db:
        prog_doc = db.collection('user_progress').document(uid).collection('skills').document(current_skill_id).get()
        if prog_doc.exists:
            p_data = prog_doc.to_dict()
            mastery = p_data.get("mastery", 0.0)
            attempts = p_data.get("attempts", 0)

    # 3. Answer Evaluation
    evaluation_result = None
    if len(history) >= 1 and user_message and user_message.lower() != 'start':
        try:
            eval_prompt = f"""Evaluate student's math answer.
Context: Teaching {lesson_ctx.get('title') if lesson_ctx else 'Math'}
Student Answer: "{user_message}"
Previous AI Message: "{history[-1].get('content') if history else ''}"

Return ONLY valid JSON:
{{
  "is_correct": boolean,
  "feedback_type": "reinforce" | "correct" | "hint",
  "mastery_delta": float (-0.1 to 0.2)
}}
"""
            eval_resp = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "system", "content": eval_prompt}],
                response_format={"type": "json_object"}
            )
            evaluation_result = json.loads(eval_resp.choices[0].message.content)
            
            if uid and current_skill_id and db:
                new_mastery = max(0, min(1.0, mastery + evaluation_result.get("mastery_delta", 0)))
                db.collection('user_progress').document(uid).collection('skills').document(current_skill_id).set({
                    "mastery": new_mastery,
                    "attempts": attempts + 1,
                    "last_updated": firestore.SERVER_TIMESTAMP
                }, merge=True)
                mastery = new_mastery
        except Exception as e:
            print(f"Eval Error: {e}")

    # 4. Build Pedagogical Prompt
    standard_info = f"Standard: {lesson_ctx.get('title')}\nDescription: {lesson_ctx.get('description')}" if lesson_ctx else ""
    skill_info = ""
    if lesson_ctx and current_skill_id:
        skill = next((s for s in lesson_ctx.get("skills", []) if s['id'] == current_skill_id), None)
        if skill:
            skill_info = f"Current Skill: {skill['title']}\nObjective: {skill['description']}\nDifficulty: {skill['difficulty']}/5"

    # 5. Determine Grade Level Rules
    user_grade = str(user_profile.get('grade', '6'))
    grade_int = 6
    if user_grade.upper() == 'K':
        grade_int = 0
    elif user_grade.isdigit():
        grade_int = int(user_grade)
        
    level_rules = ""
    if grade_int <= 5:
        level_rules = """🔹 ELEMENTARY SCHOOL TACTICS:
- Use physical objects (fruits, pencils, money) for examples.
- Ask counting questions and use visual grouping logic.
- Start heavily with stories (e.g., sharing apples) before transitioning to symbols (+, -, x, /).
- Use base-10 explanations, connect fractions to real objects (pizza, cake), and decimals to money.
- Use real-life scenarios (shopping, cooking) for measurement."""
    elif grade_int <= 8:
        level_rules = """🔹 MIDDLE SCHOOL TACTICS:
- Use real-world problems (discounts, speed) and gradually move to algebraic form.
- Actively use number lines. Emphasize rules of signs.
- Explain "why solving works", don't just give steps.
- Connect tables -> graphs -> equations clearly.
- Use datasets relevant to the student for statistics."""
    else:
        level_rules = """🔹 HIGH SCHOOL TACTICS:
- Show explicit step-by-step solving and emphasize pattern recognition.
- Teach logical reasoning step-by-step for proofs and geometry.
- Connect math to real scenarios (finance, growth).
- Explain the MEANING of statistics, not just calculations.
- Focus on intuition (rates of change, accumulation) over memorization."""

    system_content = f"""You are Nova, an elite Socratic AI Mathematics Tutor.
Student Name: {user_name}
Country: {user_profile.get('country', 'International')}
Grade: {user_profile.get('grade', '6')}
{standard_info}
{skill_info}
Current Mastery: {int(mastery * 100)}%

{level_rules}

====================
🧠 ADAPTIVE LEARNING LOGIC
====================
IF student struggles:
→ Reduce difficulty, use simpler numbers, re-explain differently.

IF student succeeds:
→ Increase complexity, introduce multi-step problems.

🎯 END CONDITION: A concept is considered MASTERED ONLY if:
1. Student answers 3-5 varied questions correctly.
2. They can successfully explain their reasoning.

====================
🧩 LESSON STRUCTURE (MANDATORY FORMAT)
====================
Follow this sequence strictly for EVERY lesson:
1. Concept Introduction
2. Intuition Building (real-world analogy)
3. Core Explanation
4. Worked Examples (step-by-step)
5. Guided Practice
6. Independent Practice
7. Mastery Check (Ask them to explain!)
8. Challenge Extension (if mastered)

====================
CORE PEDAGOGY & FINAL INSTRUCTION
====================
- Teach ONE tiny concept at a time.
- After every explanation, ask ONE specific question to check understanding.
- NEVER give the full answer. Use visual or real-world hints.
- Teach interactively. NEVER lecture.

BOARD INSTRUCTIONS:
Speech: 1-2 warm sentences. No symbols.
Board: Use [[WRITE: "content"]]
- ALL CAPS TITLES.
- $...$ for equations.

STATE MANAGEMENT:
- Evaluation: {evaluation_result if evaluation_result else "First turn"}
- If CORRECT: Praise and move to next sub-topic or harder variation.
- If INCORRECT: Gently point out error and provide a simpler example.

Do NOT use labels "Speech:" or "Board:". Talk naturally, then use [[WRITE]].
"""

    messages = [{"role": "system", "content": system_content}]
    for msg in history[-10:]:
        role = msg.get("role")
        content = msg.get("content")
        if role and content:
            messages.append({"role": role, "content": content})

    if user_message.lower() == 'start':
        user_message = f"Hi Nova! I'm ready to learn {lesson_ctx.get('title') if lesson_ctx else 'math'}. Please introduce the first concept."

    messages.append({"role": "user", "content": user_message})

    def generate():
        try:
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=600,
                temperature=0.7,
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
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
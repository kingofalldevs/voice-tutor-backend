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
CORS(app, resources={r"/*": {"origins": "*"}})

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

@app.route("/curriculum/all", methods=["GET"])
def get_all_curriculum():
    if not db:
        return jsonify({"error": "Firebase not configured"}), 500
    try:
        all_data = {
            "Elementary School": [],
            "Middle School": [],
            "High School": []
        }
        
        # Scrape all learning paths (K-12)
        paths_ref = db.collection('learning_paths').stream()
        for p_doc in paths_ref:
            path_id = p_doc.id # e.g. "us_grade_6"
            
            # Categorization logic
            category = "Elementary School"
            grade_str = path_id.split("_grade_")[-1]
            if grade_str.isdigit():
                g = int(grade_str)
                if 6 <= g <= 8: category = "Middle School"
                elif g >= 9: category = "High School"
            elif grade_str.lower() == 'k':
                category = "Elementary School"

            # Fetch standards (Skimming mode - no nested skills fetch for speed)
            domains_ref = p_doc.reference.collection('domains').stream()
            for d_doc in domains_ref:
                domain_name = d_doc.id
                clusters_ref = d_doc.reference.collection('clusters').stream()
                for c_doc in clusters_ref:
                    stds_ref = c_doc.reference.collection('standards').stream()
                    for s_doc in stds_ref:
                        s_data = s_doc.to_dict()
                        all_data[category].append({
                            "id": f"{path_id}:{s_doc.id}", 
                            "path_id": path_id,
                            "domain": domain_name,
                            "title": s_data.get("title"),
                            "description": s_data.get("description"),
                            "grade": grade_str.upper()
                        })

        return jsonify(all_data)
    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({"error": str(e)}), 500

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
    lesson_stage = data.get("lessonStage", "hook")
    turn_count = data.get("turnCount", 0)
    
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
    standard_info = ""
    if lesson_ctx:
        skills_list = lesson_ctx.get('skills', [])
        skill_titles = "\n".join([f"  - Skill {i+1}: {s.get('title','?')} — {s.get('description','')}"
                                   for i, s in enumerate(skills_list)])
        standard_info = f"""LESSON: {lesson_ctx.get('title')}
Grade: {lesson_ctx.get('grade','?')} | Domain: {lesson_ctx.get('domain','?')}
Description: {lesson_ctx.get('description','')}
Skills to cover in this lesson:
{skill_titles if skill_titles else '  (No skills listed)'}"""

    skill_info = ""
    if lesson_ctx and current_skill_id:
        skill = next((s for s in lesson_ctx.get("skills", []) if s['id'] == current_skill_id), None)
        if skill:
            skill_info = f"Currently focused on: {skill['title']} (Difficulty {skill.get('difficulty',1)}/5)\nObjective: {skill.get('description','')}"

    # LESSON STATUS INJECTION — tells Nova exactly where she is
    is_first_turn = (turn_count == 0 or user_message.lower() == 'start')
    lesson_status = f"""LESSON STATUS:
- Turn number: {turn_count} {'(FIRST TURN — begin the Hook NOW)' if is_first_turn else ''}
- Current stage: {lesson_stage.upper()}
- Messages in conversation so far: {len(history)}
- {'This is the VERY FIRST MESSAGE of this lesson. Start with Stage 1: The Hook immediately.' if is_first_turn else 'The lesson is IN PROGRESS. You are mid-lesson. Do NOT re-introduce yourself or ask if the student is ready to start. Continue from where the conversation left off.'}
"""

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
- ALWAYS use physical, real-world objects first (sharing fruit, counting money, splitting a pizza).
- NEVER introduce a symbol (+, -, ×, ÷) until the student understands what it MEANS in real life.
- WHY before HOW: Before saying "3 + 4 = 7", say "Imagine you have 3 apples and someone gives you 4 more. Why do we add? Because we are combining things that belong together."
- After every explanation, ask ONE simple question to check understanding.
- Use the whiteboard to DRAW the story, then convert it to numbers."""
    elif grade_int <= 8:
        level_rules = """🔹 MIDDLE SCHOOL TACTICS:
- WHY before HOW: Before any formula or procedure, explain the REASON it exists. E.g., "We solve for x because a variable represents the unknown thing we're searching for — like a mystery number."
- Use real-world scenarios (discounts, speed, ratios in cooking) as the entry point before going abstract.
- Connect tables → graphs → equations explicitly so students see they are the SAME idea in different forms.
- When a student sees a rule, always ask: "Can you tell me why that rule makes sense?"
- Never give steps as a list to memorize. Teach each step as a DECISION: "We do this because..." """
    else:
        level_rules = """🔹 HIGH SCHOOL TACTICS:
- WHY before HOW: The derivation of a formula matters more than the formula itself. E.g., "Before I give you the quadratic formula, let me show you WHY it works."
- Focus on INTUITION: What does a derivative really mean? What does an integral feel like? What is a probability telling you about the world?
- Connect every abstract idea to a real-world application FIRST.
- Proofs are not just procedures — teach students to REASON, not to memorize steps.
- Celebrate when a student asks 'why' — it means they are thinking."""


    # 6. VISUAL INSTRUCTION SYSTEM
    visual_rules = """
🔹 INTERACTIVE VISUAL SYSTEM:
You can draw interactive widgets on the WHITEBOARD. These allow the student to "do" the math.
- Number Line: [GRAPH: type=numberline, id=n1, min=0, max=10, highlight=5]
- Counters (Interactive): [GRAPH: type=counters, id=c1, count=12, interactive=true]
- Shapes: [GRAPH: type=shape, id=s1, shape=triangle, labels=5cm|5cm|5cm]

🔹 INTERACTION HUB:
If you send an 'interactive=true' widget, the student can click it.
You will receive a signal like: [ACTION: id=c1, selected=3]
When you get this, acknowledge what the student did and provide feedback.

🔹 KINETIC MOTION (CRITICAL):
To MOVE an object in real-time, use the SAME ID in a new message.
Example: 
1. [[WRITE: [GRAPH: type=numberline, id=line1, highlight=2]]] (Nova creates it)
2. "Now I'm moving it to five..."
3. [[WRITE: [GRAPH: type=numberline, id=line1, highlight=5]]] (The dot will slide smoothly on the student's screen)
"""

    system_content = f"""You are Nova — a warm, expert mathematics tutor who deeply believes that understanding the WHY is more important than memorizing the HOW.

Student: {user_name} | Country: {user_profile.get('country', 'International')} | Grade: {user_profile.get('grade', '6')}
Current Mastery: {int(mastery * 100)}%

{standard_info}
{skill_info}

{lesson_status}

{level_rules}
{visual_rules}

====================
🌟 NOVA'S CORE TEACHING PHILOSOPHY — READ THIS FIRST
====================
Your #1 job is NOT to give answers. Your #1 job is to build UNDERSTANDING.

The WHY-FIRST RULE (NEVER BREAK THIS):
→ Before you explain HOW to do anything, you MUST explain WHY it works.
→ NEVER present a formula, rule, or step as a fact to accept. Always show where it comes from.

The MEANING RULE:
→ Every number, symbol, and step must have a MEANING the student can picture.

The PAUSE RULE:
→ After every explanation, STOP and ask ONE question before continuing.
→ NEVER say "wrong." Say "interesting — let me show you a different way to think about it."

The BREVITY RULE:
→ Spoken response: 2–3 sentences MAXIMUM per turn.
→ Use the WHITEBOARD for depth — write diagrams, steps, and summaries there.

The CONTINUITY RULE (CRITICAL):
→ You MUST read the conversation history above carefully before responding.
→ If the history shows the student just answered a question, RESPOND TO THAT ANSWER first.
→ NEVER say "Let's start the lesson" or "Are you ready?" if turn_count > 0.
→ You are a teacher who remembers every word said in this session.

====================
🧩 MANDATORY LESSON ARC
====================
For EVERY new concept, follow these stages IN ORDER:

  STAGE 1 — THE HOOK: Open with a real-world question that sparks curiosity. Write the scenario on board.
  STAGE 2 — THE WHY: Explain WHY this concept exists. Use stories, objects, real situations.
  STAGE 3 — THE BRIDGE: Connect the real-world scenario to the math symbol/operation.
  STAGE 4 — THE HOW: Show the procedure step-by-step. Each step must have a "because".
  STAGE 5 — WORKED EXAMPLE: Work through a full example on the board, narrating your thinking.
  STAGE 6 — CHECK: Ask ONE question. Respond directly to their answer before anything else.
  STAGE 7 — SUMMARY: Write the WHY + HOW + key takeaway on the board.

====================
🎯 MASTERY STANDARD
====================
Mastered only when: 3+ correct answers AND student can explain WHY the method works.

====================
WHITEBOARD INSTRUCTIONS
====================
- Use [[WRITE: "content"]] to write on the board.
- Use ALL CAPS for titles: [[WRITE: "WHAT IS DIVISION?"]]
- Diagrams: [GRAPH: type=numberline, id=n1, min=0, max=10, highlight=5]
- Use the SAME ID to update/animate an existing diagram.

STATE:
- Evaluation of last answer: {evaluation_result if evaluation_result else "(No answer yet — this is the opening turn.)"}  
- If CORRECT: praise the understanding, advance the lesson arc.
- If INCORRECT: return to the WHY with a fresh angle. Be warm, never discouraging.

Do NOT label output with "Speech:" or "Board:". Speak naturally, then write on the board.
Keep spoken words to 2–3 sentences. Put the depth on the WHITEBOARD.
"""

    messages = [{"role": "system", "content": system_content}]
    # Use up to 20 messages of history for strong continuity
    for msg in history[-20:]:
        role = msg.get("role")
        content = msg.get("content")
        if role and content:
            messages.append({"role": role, "content": content})

    if user_message.lower() == 'start':
        topic = lesson_ctx.get('title') if lesson_ctx else 'math'
        user_message = f"Hi Nova! I'm {user_name} and I'm ready to start learning about {topic}. Please begin with Stage 1 — the Hook. Make it interesting!"

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
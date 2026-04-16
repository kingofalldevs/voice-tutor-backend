import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import json

# Initialize Firebase
def init_fb():
    cred_path = 'serviceAccount.json'
    if not os.path.exists(cred_path):
        raise FileNotFoundError("serviceAccount.json missing")
    cred = credentials.Certificate(cred_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_fb()

def add_standard(path_id, domain, cluster, std_id, std_data, skills):
    print(f"  [{path_id}] Adding Standard: {std_id} - {std_data['title']}")
    std_ref = db.collection('learning_paths').document(path_id) \
                .collection('domains').document(domain) \
                .collection('clusters').document(cluster) \
                .collection('standards').document(std_id)
    
    std_ref.set({
        "id": std_id,
        "title": std_data['title'],
        "description": std_data['description'],
        "domain": domain,
        "updatedAt": datetime.utcnow()
    })
    
    for skill in skills:
        std_ref.collection('skills').document(skill['id']).set(skill)

def seed_us_curriculum():
    grades = {
        "K": ["Counting & Cardinality", "Operations & Algebraic Thinking", "Number & Operations in Base Ten", "Measurement & Data", "Geometry"],
        "1": ["Operations & Algebraic Thinking", "Number & Operations in Base Ten", "Measurement & Data", "Geometry"],
        "2": ["Operations & Algebraic Thinking", "Number & Operations in Base Ten", "Measurement & Data", "Geometry"],
        "3": ["Operations & Algebraic Thinking", "Number & Operations in Base Ten", "Number & Operations—Fractions", "Measurement & Data", "Geometry"],
        "4": ["Operations & Algebraic Thinking", "Number & Operations in Base Ten", "Number & Operations—Fractions", "Measurement & Data", "Geometry"],
        "5": ["Operations & Algebraic Thinking", "Number & Operations in Base Ten", "Number & Operations—Fractions", "Measurement & Data", "Geometry"],
        "6": ["Ratios & Proportional Relationships", "The Number System", "Expressions & Equations", "Geometry", "Statistics & Probability"],
        "7": ["Ratios & Proportional Relationships", "The Number System", "Expressions & Equations", "Geometry", "Statistics & Probability"],
        "8": ["The Number System", "Expressions & Equations", "Functions", "Geometry", "Statistics & Probability"],
        "9": ["Algebra 1 - Number & Quantity", "Algebra 1 - Algebra", "Algebra 1 - Functions", "Algebra 1 - Statistics"],
        "10": ["Geometry - Congruence", "Geometry - Similarity", "Geometry - Circles", "Geometry - Modeling"],
        "11": ["Algebra 2 - Number & Quantity", "Algebra 2 - Algebra", "Algebra 2 - Functions"],
        "12": ["Calculus - Limits", "Calculus - Derivatives", "Calculus - Integrals"]
    }

    descriptions = {
        "Counting & Cardinality": "Know number names and the count sequence.",
        "Operations & Algebraic Thinking": "Understand addition/subtraction and properties of operations.",
        "Number & Operations in Base Ten": "Understand the place value system.",
        "Measurement & Data": "Describe and compare measurable attributes.",
        "Geometry": "Identify and describe shapes.",
        "Number & Operations—Fractions": "Develop understanding of fractions as numbers.",
        "Ratios & Proportional Relationships": "Understand ratio concepts and use ratio reasoning.",
        "The Number System": "Compute fluently and find common factors/multiples.",
        "Expressions & Equations": "Work with variables and solve equations.",
        "Functions": "Define, evaluate, and compare functions.",
        "Statistics & Probability": "Summarize and describe distributions.",
        "Algebra 1 - Algebra": "Seeing Structure in Expressions and Reasoning with Equations.",
        "Geometry - Modeling": "Applying geometric concepts in modeling situations.",
        "Calculus - Derivatives": "Understanding rates of change."
    }

    for grade, domains in grades.items():
        path_id = f"us_grade_{grade.lower()}"
        print(f"🌱 Seeding US Grade {grade}...")
        db.collection('learning_paths').document(path_id).set({
            "id": path_id,
            "country": "US",
            "grade": grade,
            "title": f"US Common Core Grade {grade} - Math",
            "updatedAt": datetime.utcnow()
        })

        for domain in domains:
            desc = descriptions.get(domain, f"Master {domain} concepts for Grade {grade}.")
            std_id = f"US.{grade}.{domain[:2].upper()}.1"
            add_standard(
                path_id, domain, "Core Concepts", std_id,
                {"title": f"Intro to {domain}", "description": desc},
                [
                    {"id": f"us_{grade}_{std_id}_s1", "title": "Fundamentals", "description": f"Master the basics of {domain}.", "difficulty": 1, "prerequisites": []},
                    {"id": f"us_{grade}_{std_id}_s2", "title": "Applications", "description": f"Solve real-world problems involving {domain}.", "difficulty": 3, "prerequisites": [f"us_{grade}_{std_id}_s1"]}
                ]
            )

def seed_ghana_curriculum():
    grades = ["P1", "P2", "P3", "P4", "P5", "P6", "JHS1", "JHS2", "JHS3", "SHS1", "SHS2", "SHS3"]
    strands = ["Number", "Algebra", "Geometry and Measurement", "Data"]
    
    descriptions = {
        "Number": "Developing numeracy and operation skills.",
        "Algebra": "Patterns, relations and algebraic expressions.",
        "Geometry and Measurement": "Exploring shapes, space and measurement units.",
        "Data": "Handling data and understanding probability."
    }

    for grade in grades:
        path_id = f"ghana_grade_{grade.lower()}"
        print(f"🇬🇭 Seeding Ghana Grade {grade}...")
        db.collection('learning_paths').document(path_id).set({
            "id": path_id,
            "country": "Ghana",
            "grade": grade,
            "title": f"Ghana GES Grade {grade} - Math",
            "updatedAt": datetime.utcnow()
        })

        for strand in strands:
            std_id = f"GH.{grade}.{strand[:2].upper()}.1"
            add_standard(
                path_id, strand, "Core Strands", std_id,
                {"title": f"Foundations of {strand}", "description": descriptions[strand]},
                [
                    {"id": f"gh_{grade}_{std_id}_s1", "title": "Basics", "description": f"Understanding {strand} at the {grade} level.", "difficulty": 1, "prerequisites": []},
                    {"id": f"gh_{grade}_{std_id}_s2", "title": "Advanced Practice", "description": f"Solve {strand} problems.", "difficulty": 2, "prerequisites": [f"gh_{grade}_{std_id}_s1"]}
                ]
            )

def seed_all():
    print("🚀 GLOBAL CURRICULUM SEEDING START...")
    seed_us_curriculum()
    # seed_ghana_curriculum()  # Disabled per user request
    print("✨ ALL CURRICULA SEEDING COMPLETE!")

if __name__ == "__main__":
    seed_all()

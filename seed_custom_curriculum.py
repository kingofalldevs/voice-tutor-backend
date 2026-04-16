import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os

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

def add_standard(path_id, domain, std_id, std_data, skills):
    print(f"  [{path_id}] Adding Standard: {std_id} - {std_data['title']}")
    
    # Ensure Domain document exists with fields
    domain_ref = db.collection('learning_paths').document(path_id).collection('domains').document(domain)
    domain_ref.set({"name": domain, "active": True}, merge=True)
    
    # Ensure Cluster document exists with fields
    cluster_ref = domain_ref.collection('clusters').document("Core")
    cluster_ref.set({"name": "Core"}, merge=True)
    
    # Set Standard data
    std_ref = cluster_ref.collection('standards').document(std_id)
    std_ref.set({
        "id": std_id,
        "title": std_data['title'],
        "description": std_data['description'],
        "domain": domain,
        "updatedAt": datetime.utcnow()
    })
    
    for skill in skills:
        std_ref.collection('skills').document(skill['id']).set(skill)

def seed_custom_curriculum():
    print("🚀 SEEDING CUSTOM CURRICULUM TREE...")

    curriculum = {
        "elementary": {
            "grades": ["K", "1", "2", "3", "4", "5"],
            "strands": [
                {
                    "domain": "Counting & Number Sense",
                    "concepts": "One-to-one correspondence, Counting (forward, backward, skip counting), Number recognition (0–1000+), Comparing numbers (>, <, =)"
                },
                {
                    "domain": "Operations",
                    "concepts": "Addition (within 100 → 1000), Subtraction, Multiplication (repeated addition), Division (sharing & grouping)"
                },
                {
                    "domain": "Place Value & Number System",
                    "concepts": "Ones, tens, hundreds, thousands, Expanded form, Fractions (intro: parts of a whole), Decimals (money-based)"
                },
                {
                    "domain": "Measurement",
                    "concepts": "Time (reading clocks), Money (counting, making change), Length, mass, capacity"
                },
                {
                    "domain": "Geometry",
                    "concepts": "2D shapes, 3D shapes, Basic angles"
                }
            ]
        },
        "middle": {
            "grades": ["6", "7", "8"],
            "strands": [
                {
                    "domain": "Ratios & Proportions",
                    "concepts": "Ratios, Rates, Percentages, Proportions"
                },
                {
                    "domain": "Number System",
                    "concepts": "Integers (including negatives), Rational numbers, Irrational numbers (intro), Exponents"
                },
                {
                    "domain": "Expressions & Equations",
                    "concepts": "Simplifying expressions, Linear equations, Inequalities"
                },
                {
                    "domain": "Functions",
                    "concepts": "Definition of a function, Linear functions, Graphing (Cartesian plane)"
                },
                {
                    "domain": "Geometry",
                    "concepts": "Area, surface area, volume, Transformations"
                },
                {
                    "domain": "Statistics & Probability",
                    "concepts": "Mean, median, mode, Basic probability"
                }
            ]
        },
        "high": {
            "grades": ["9", "10", "11", "12"],
            "strands": [
                {
                    "domain": "Algebra I & II",
                    "concepts": "Linear equations, Quadratics, Polynomials, Systems of equations, Exponentials, Complex numbers"
                },
                {
                    "domain": "Geometry",
                    "concepts": "Proofs, Congruence & similarity, Trigonometry"
                },
                {
                    "domain": "Functions & Modeling",
                    "concepts": "Linear, quadratic, exponential, logarithmic functions, Real-world modeling"
                },
                {
                    "domain": "Statistics & Probability",
                    "concepts": "Distributions, Data analysis, Inference"
                },
                {
                    "domain": "Pre-Calculus & Calculus",
                    "concepts": "Limits, Derivatives, Integrals"
                }
            ]
        }
    }

    country = "US"

    for level, data in curriculum.items():
        grades = data["grades"]
        strands = data["strands"]
        
        for grade in grades:
            path_id = f"{country.lower()}_grade_{grade.lower()}"
            print(f"🌱 Seeding {level.title()} School - Grade {grade} ({path_id})...")
            
            db.collection('learning_paths').document(path_id).set({
                "id": path_id,
                "country": country,
                "grade": grade,
                "title": f"Nova Academy Grade {grade}",
                "updatedAt": datetime.utcnow()
            })

            for idx, strand in enumerate(strands):
                domain = strand["domain"]
                concepts = strand["concepts"]
                std_id = f"NOVA.{grade}.{domain[:3].upper()}.{idx+1}"
                
                # Split concepts into individual skills
                concept_list = [c.strip() for c in concepts.split(",")]
                skills = []
                for s_idx, concept in enumerate(concept_list):
                    skills.append({
                        "id": f"{std_id}_s{s_idx+1}",
                        "title": concept,
                        "description": f"Master the concept of {concept}.",
                        "difficulty": (s_idx % 3) + 1,
                        "prerequisites": []
                    })

                add_standard(
                    path_id, domain, std_id,
                    {"title": domain, "description": f"Encompasses: {concepts}"},
                    skills
                )

if __name__ == "__main__":
    seed_custom_curriculum()
    print("✨ ALL CUSTOM CURRICULA SEEDING COMPLETE!")

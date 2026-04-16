import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import sys

# ================= INITIALIZE FIREBASE =================
def initialize_firebase():
    cred_path = 'serviceAccount.json'
    
    if not os.path.exists(cred_path):
        print("❌ Error: serviceAccount.json not found.")
        sys.exit(1)

    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully")
        return firestore.client()
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        sys.exit(1)

db = initialize_firebase()

# ================= LESSON DATA =================
lessons = [
    # PRIMARY 5
    {
        "title": "Numbers and Place Value",
        "subject": "Mathematics",
        "gradeLevel": "Primary 5",
        "coverEmoji": "🔢",
        "chapterCount": 3,
        "chapters": [
            {"id": 1, "title": "Reading and Writing Large Numbers", "summary": "Learn how to read and write numbers up to millions using place value."},
            {"id": 2, "title": "Place Value and Rounding", "summary": "Understand digits in ones, tens, hundreds and round numbers correctly."},
            {"id": 3, "title": "Comparing Numbers", "summary": "Use greater than and less than signs to compare numbers."}
        ]
    },
    {
        "title": "Basic Operations",
        "subject": "Mathematics",
        "gradeLevel": "Primary 5",
        "coverEmoji": "➕",
        "chapterCount": 3,
        "chapters": [
            {"id": 1, "title": "Addition and Subtraction", "summary": "Solve large number problems using addition and subtraction."},
            {"id": 2, "title": "Multiplication and Division", "summary": "Multiply and divide numbers including word problems."},
            {"id": 3, "title": "Word Problems", "summary": "Apply math operations to real-life situations like shopping."}
        ]
    },
    {
        "title": "Fractions and Decimals",
        "subject": "Mathematics",
        "gradeLevel": "Primary 5",
        "coverEmoji": "🍰",
        "chapterCount": 3,
        "chapters": [
            {"id": 1, "title": "Understanding Fractions", "summary": "Learn numerators and denominators using visual examples."},
            {"id": 2, "title": "Equivalent Fractions", "summary": "Find and compare fractions with the same value."},
            {"id": 3, "title": "Introduction to Decimals", "summary": "Convert simple fractions into decimals and understand place value."}
        ]
    },
    {
        "title": "Measurement",
        "subject": "Mathematics",
        "gradeLevel": "Primary 5",
        "coverEmoji": "📏",
        "chapterCount": 3,
        "chapters": [
            {"id": 1, "title": "Length, Mass, and Capacity", "summary": "Measure using meters, kilograms, and liters."},
            {"id": 2, "title": "Time", "summary": "Tell time and calculate durations."},
            {"id": 3, "title": "Money", "summary": "Solve problems using standard currency and making change."}
        ]
    },
    {
        "title": "Geometry",
        "subject": "Mathematics",
        "gradeLevel": "Primary 5",
        "coverEmoji": "📐",
        "chapterCount": 3,
        "chapters": [
            {"id": 1, "title": "Angles and Lines", "summary": "Identify acute, obtuse, and right angles."},
            {"id": 2, "title": "2D Shapes", "summary": "Learn properties of squares, rectangles, and triangles."},
            {"id": 3, "title": "Perimeter and Area", "summary": "Calculate the boundary and space of shapes."}
        ]
    },
    {
        "title": "Data and Patterns",
        "subject": "Mathematics",
        "gradeLevel": "Primary 5",
        "coverEmoji": "📊",
        "chapterCount": 3,
        "chapters": [
            {"id": 1, "title": "Reading Charts", "summary": "Interpret bar graphs and tables."},
            {"id": 2, "title": "Drawing Graphs", "summary": "Create simple bar charts from data."},
            {"id": 3, "title": "Number Patterns", "summary": "Identify and continue number sequences."}
        ]
    }
]

# ================= SEED FUNCTION =================
def seed_lessons():
    print("\n🚀 Starting lesson seeding...\n")

    batch = db.batch()
    added = 0
    skipped = 0

    for lesson in lessons:
        try:
            # Check duplicates (title + gradeLevel)
            existing = db.collection('lessons') \
                .where('title', '==', lesson['title']) \
                .where('gradeLevel', '==', lesson['gradeLevel']) \
                .stream()

            if any(existing):
                print(f"⏩ Skipped: {lesson['title']} ({lesson['gradeLevel']})")
                skipped += 1
                continue

            # Add metadata
            lesson['createdAt'] = datetime.utcnow()
            lesson['updatedAt'] = datetime.utcnow()

            doc_ref = db.collection('lessons').document()
            batch.set(doc_ref, lesson)

            print(f"✅ Queued: {lesson['title']}")
            added += 1

        except Exception as e:
            print(f"❌ Error processing {lesson['title']}: {e}")

    # Commit batch
    try:
        batch.commit()
        print("\n📦 Batch committed successfully!")
    except Exception as e:
        print(f"❌ Batch commit failed: {e}")

    print("\n🏁 DONE")
    print(f"✅ Added: {added}")
    print(f"⏩ Skipped: {skipped}")
    print("🤖 Nova is ready to teach.")

# ================= RUN =================
if __name__ == "__main__":
    seed_lessons()
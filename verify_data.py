import firebase_admin
from firebase_admin import credentials, firestore
import os

def init_fb():
    cred_path = 'serviceAccount.json'
    if not os.path.exists(cred_path):
        return None
    cred = credentials.Certificate(cred_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_fb()
if db:
    path_id = 'us_grade_6'
    doc = db.collection('learning_paths').document(path_id).get()
    if doc.exists:
        print(f"Path {path_id} exists.")
        domains = db.collection('learning_paths').document(path_id).collection('domains').stream()
        count = 0
        for d in domains:
            print(f"Domain found: {d.id}")
            count += 1
        print(f"Total domains for {path_id}: {count}")
    else:
        print(f"Path {path_id} NOT FOUND.")
else:
    print("DB Connection failed.")

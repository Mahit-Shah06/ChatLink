import requests
from bot.core.pw_utils.utils import get_auth_headers, BASE_URL

def fetch_batches(token, page=1):
    """
    Fetch user-purchased batches.
    Returns list of dicts: name, slug, startDate, endDate, expiryDate.
    """
    url = f"{BASE_URL}/batch-service/v1/batches/purchased-batches?amount=paid&page={page}&type=ALL"
    headers = get_auth_headers(token)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        if data.get("success") and isinstance(data.get("data"), list):
            return [
                {
                    "name": batch.get("name"),
                    "slug": batch.get("slug"),
                    "startDate": batch.get("startDate"),
                    "endDate": batch.get("endDate"),
                    "expiryDate": batch.get("expiryDate", "")
                }
                for batch in data["data"]
            ]
        return []
    except Exception as e:
        return []

def fetch_subjects(token, batch_slug):
    """
    Fetches all subjects for a given batch.
    Returns list of subject dicts: 
        _id, subject, slug, teacherIds (list of dicts), tagCount, displayOrder, lectureCount.
    """
    url = f"{BASE_URL}/v3/batches/{batch_slug}/details"
    headers = get_auth_headers(token)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        subjects = data.get("data", {}).get("subjects", [])
        res = []
        for s in subjects:
            res.append({
                "_id": s.get("_id"),
                "subject": s.get("subject"),
                "slug": s.get("slug"),
                "teacherIds": [
                    {
                        "firstName": t.get("firstName"),
                        "lastName": t.get("lastName"),
                        "experience": t.get("experience"),
                        "qualification": t.get("qualification"),
                        "email": t.get("email")
                    }
                    for t in s.get("teacherIds", [])
                ],
                "tagCount": s.get("tagCount"),
                "displayOrder": s.get("displayOrder"),
                "lectureCount": s.get("lectureCount")
            })
        return res
    except Exception as e:
        return []

def fetch_topics(token, batch_slug, subject_slug, page=1):
    """
    Fetch topics/chapters for a subject in a batch.
    Returns list of topic dicts: 
        _id, name, displayOrder, notes, exercises, videos, lectureVideos, slug.
    """
    url = f"{BASE_URL}/v2/batches/{batch_slug}/subject/{subject_slug}/topics?page={page}"
    headers = get_auth_headers(token)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        topics = data.get("data", [])
        return [
            {
                "_id": t.get("_id"),
                "name": t.get("name"),
                "displayOrder": t.get("displayOrder"),
                "notes": t.get("notes"),
                "exercises": t.get("exercises"),
                "videos": t.get("videos"),
                "lectureVideos": t.get("lectureVideos"),
                "slug": t.get("slug")
            }
            for t in topics
        ]
    except Exception as e:
        return []

def fetch_notes(token, batch_slug, subject_slug, topic_slug, page=1):
    """
    Fetch notes (attachments) for a given topic in a subject of a batch.
    Returns a list of dicts:
        - topic: topic name
        - attachments: list of dicts with _id, baseUrl, key, name
    """
    url = (f"{BASE_URL}/v2/batches/{batch_slug}/subject/{subject_slug}"
           f"/contents?page={page}&contentType=notes&tag={topic_slug}")
    headers = get_auth_headers(token)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        notes_list = []
        for entry in data.get("data", []):
            for hw in entry.get("homeworkIds", []):
                notes_list.append({
                    "topic": hw.get("topic"),
                    "attachments": [
                        {
                            "_id": att.get("_id"),
                            "baseUrl": att.get("baseUrl"),
                            "key": att.get("key"),
                            "name": att.get("name"),
                        }
                        for att in hw.get("attachmentIds", [])
                    ]
                })
        return notes_list
    except Exception:
        return []

def fetch_dpp(token, batch_slug, subject_slug, topic_slug, page=1):
    """
    Fetch DPP Notes (attachments) for a given topic in a subject of a batch.
    Returns a list of dicts:
        - topic: topic name
        - attachments: list of dicts with _id, baseUrl, key, name
    """
    url = (f"{BASE_URL}/v2/batches/{batch_slug}/subject/{subject_slug}"
           f"/contents?page={page}&contentType=DppNotes&tag={topic_slug}")
    headers = get_auth_headers(token)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        dpp_list = []
        for entry in data.get("data", []):
            for hw in entry.get("homeworkIds", []):
                dpp_list.append({
                    "topic": hw.get("topic"),
                    "attachments": [
                        {
                            "_id": att.get("_id"),
                            "baseUrl": att.get("baseUrl"),
                            "key": att.get("key"),
                            "name": att.get("name"),
                        }
                        for att in hw.get("attachmentIds", [])
                    ]
                })
        return dpp_list
    except Exception:
        return []


def get_dpp_quiz_attempt_id(token, batch_id, subject_id, topic_id, page=1, limit=50):
    """
    Fetch the attempt ID for a DPP-Quiz for a given topic, if it exists.
    Returns the attempt ID as a string, or None if unattempted.
    """
    url = (f"{BASE_URL}/v3/test-service/tests/dpp?"
           f"page={page}&limit={limit}&batchId={batch_id}&batchSubjectId={subject_id}"
           f"&isSubjective=false&chapterId={topic_id}")
    headers = get_auth_headers(token)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        for entry in data.get("data", []):
            test_mapping = entry.get("testStudentMapping", {})
            attempt_id = test_mapping.get("_id")
            if attempt_id:
                return attempt_id
        return None
    except Exception:
        return None

def fetch_dpp_quiz_questions(token, attempt_id):
    """
    Fetch questions for an attempted DPP-Quiz using its attempt ID.
    Returns list of dicts:
        - _id (question id)
        - questionNumber
        - images (list of attachment dicts)
        - options (list of { _id, en })
        - solution_option_ids (list, matches options' _id)
        - difficultyLevel
        - topicName
        - solutionDescriptions (list of image dicts)
    Only questions with solutions/options found.
    """
    url = (f"{BASE_URL}/v3/test-service/tests/mapping/{attempt_id}/preview-test")
    headers = get_auth_headers(token)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        out = []
        for qwrap in data.get("data", {}).get("questions", []):
            q = qwrap.get("question", {})
            # Options
            options = [
                {"_id": opt.get("_id"),
                 "en": opt.get("texts", {}).get("en")}
                for opt in q.get("options", [])
            ]
            # Match solutions to options
            solution_ids = q.get("solutions", [])
            # Images for question
            images = []
            image_en = q.get("imageIds", {}).get("en")
            if image_en:
                images.append({
                    "_id": image_en.get("_id"),
                    "name": image_en.get("name"),
                    "baseUrl": image_en.get("baseUrl"),
                    "key": image_en.get("key")
                })
            # Solution Descriptions (images)
            solution_desc = []
            for sd in q.get("solutionDescription", []):
                sd_img = sd.get("imageIds", {}).get("en")
                if sd_img:
                    solution_desc.append({
                        "_id": sd_img.get("_id"),
                        "name": sd_img.get("name"),
                        "baseUrl": sd_img.get("baseUrl"),
                        "key": sd_img.get("key")
                    })
            out.append({
                "_id": q.get("_id"),
                "questionNumber": q.get("questionNumber"),
                "images": images,
                "options": options,
                "solution_option_ids": solution_ids,
                "difficultyLevel": q.get("difficultyLevel"),
                "topicName": (q.get("topicId") or {}).get("name"),
                "solutionDescriptions": solution_desc
            })
        return out
    except Exception:
        return []

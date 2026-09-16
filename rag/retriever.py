from __future__ import annotations
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from services.ingestion_service import all_chunks

def retrieve(project_id: str, query: str, k: int=8):
    chunks=all_chunks(project_id)
    if not chunks:return []
    corpus=[c['text'] for c in chunks]
    vec=TfidfVectorizer(stop_words='english',max_features=12000)
    X=vec.fit_transform(corpus+[query])
    scores=cosine_similarity(X[-1],X[:-1]).flatten()
    idx=scores.argsort()[::-1][:k]
    return [{**chunks[i],'score':float(scores[i])} for i in idx if scores[i]>0]

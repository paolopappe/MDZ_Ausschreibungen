import os
import json
from dotenv import load_dotenv
from typing import List, Dict
import openai

from utils.db_management import _db_manager

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

SIMILARITY_THRESHOLD = 0.35


def init_pipeline():
    """
    Wir erzeugen eine Klasse MyPipeline, die – wie früher – eine .invoke()-Methode hat.
    So ändert sich `server.py` nicht, weil wir da auch 'pipeline.invoke(...)' aufrufen.
    """
    
    def retrieve(user_input: str) -> List[Dict]:
        """
        Die reine Retrieval-Funktion, die user_input nimmt und 
        via Vectorstore ähnliche Dokumente heraussucht.
        """
        query = user_input.strip()
        res = _db_manager.vector_store.similarity_search_with_relevance_scores(
            query=query,
            k=100,
            score_threshold=SIMILARITY_THRESHOLD
        )

        outputs = []
        for doc, score in res:
            original_text = doc.metadata.pop("text", "")
            outputs.append({
                "text": original_text,
                "metadata": doc.metadata,
                "score": score
            })
        return outputs

    class MyPipeline:
        """
        Erzeugt ein Pipeline-Objekt mit .invoke(data).
        Das ist kompatibel zu Ihrer alten Server-Logik:
        
            res = pipeline.invoke({"input": query})
            return res, 200
        """
        def invoke(self, data: Dict) -> str:
            # Erwartet ein Dict mit {"input": "..."} 
            # (so war es in Ihrem alten Code per 'pipeline.invoke({"input": query})')
            user_input = data.get("input", "")
            results = retrieve(user_input)
            
            # Wir wandeln die Python-Liste in einen JSON-String um,
            # damit Flask diesen String 1:1 an den Client schicken kann.
            # Auf Client-Seite kann man dann `response.json()` aufrufen.
            json_str = json.dumps(results, ensure_ascii=False)
            return json_str

    return MyPipeline()


pipeline = init_pipeline()

from __future__ import annotations

from typing import Dict
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch.nn.functional as F

LabelMap = {
    # model labels -> our keys
    "anger": "anger",
    "fear": "fear",
    "joy": "joy",
    "love": "joy",   # map love to joy
    "sadness": "sadness",
    "surprise": "surprise",
}

class EmotionClassifier:
    def __init__(self, model_name: str = "j-hartmann/emotion-english-distilroberta-base") -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.id2label = self.model.config.id2label

    @torch.inference_mode()
    def classify(self, text: str) -> Dict[str, float]:
        if not text:
            return {"joy":0.0, "sadness":0.0, "anger":0.0, "fear":0.0, "surprise":0.0, "disgust":0.0}
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=256).to(self.device)
        logits = self.model(**inputs).logits
        probs = F.softmax(logits, dim=-1).float().cpu()[0]
        # aggregate to our schema
        out = {"joy":0.0, "sadness":0.0, "anger":0.0, "fear":0.0, "surprise":0.0, "disgust":0.0}
        for i, p in enumerate(probs):
            label = self.id2label[i].lower()
            key = LabelMap.get(label)
            if key:
                out[key] += float(p)
        # normalize to [0,1]
        # keep disgust at 0.0 for now (no label mapping)
        return out 
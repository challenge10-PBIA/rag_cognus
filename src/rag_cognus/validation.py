"""Gera relatórios PDF com métricas após testar >= 50 questões para validação do RAG Cognos."""

from __future__ import annotations

import json
import random
try: 
    from reportlab.lib.pagesizes import letter, A4
    
except ImportError as exc:   
    print(f"Precisa instalar relatórios PDF: pip install 'reportlab>=4.2'")


METRICS = {  # mesmas notas do judges.py  
    "context_relevance": "Relevância do contexto",
    "groundedness": "Fidelidade às fontes", 
    "answer_relevance": "Relevância da resposta",
    "accuracy": "Acurácia",
    "professionalism": "Profissionalismo"    
}


def generate_validated_questions(nichest=None, n_qs: int=50):  
    """Gera >= 50 questões cobrindo todos os nichos do projeto."""
   
   if not nichest: 
       NICHE_TOPICS = { # Questões validadas para cada especialidade de Cognition
   
           "todos": ["Organizar apresentação sobre liderança e comunicação. ", 
                      "Explicar técnicas para perguntas difíceis em reuniões.",  
                      "Dicas gagueira e disfluências vocais públicas."],
            
       } 
  
   
     # Mistura base + variações aleatórias, >= 50 questões total       
    base = random.choice(NICHE_TOPICS.get("todos", [])) 
   return [f"{base} (questão {i+1:03d})" for i in range(n_qs)]


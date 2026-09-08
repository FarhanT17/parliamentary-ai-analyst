import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Hardcoded answers for demo
DEMO_ANSWERS = {
    "what is the role of the prime minister": {
        "answer": "The Prime Minister is the leader of the Government. He or she is the leader of the party that wins the most seats at a general election. After a general election, the monarch calls upon the leader of the largest party to form the Government. The Prime Minister chooses the other Members of the Government and has a residence and offices at 10 Downing Street.",
        "source": "UK Parliament Glossary"
    },
    "how does parliament make laws": {
        "answer": "Parliament makes laws through a legislative process: 1) First Reading, 2) Second Reading, 3) Committee Stage, 4) Report Stage, 5) Third Reading, 6) House of Lords scrutiny, 7) Royal Assent.",
        "source": "UK Parliament Guide"
    },
    "what is the house of commons": {
        "answer": "The House of Commons is the lower house of the UK Parliament. It consists of 650 elected Members of Parliament (MPs) who represent constituencies across the UK.",
        "source": "UK Parliament Guide"
    },
    "how does the nhs work": {
        "answer": "The NHS provides healthcare free at the point of use, funded through general taxation. It includes primary care (GPs, dentists), secondary care (hospitals), and mental health services.",
        "source": "UK Government Guide"
    },
    "what is the uk's approach to climate change": {
        "answer": "The UK's approach to climate change is centered on achieving Net Zero by 2050 through the Climate Change Act 2008, Net Zero Strategy, and investment in renewable energy.",
        "source": "UK Parliament Guide"
    },
    "what is the budget": {
        "answer": "The Budget is the government's annual financial statement presented by the Chancellor of the Exchequer. It sets out plans for taxation, spending, and the economy.",
        "source": "UK Parliament Guide"
    },
    "what are the uk's immigration policies": {
        "answer": "The UK's immigration policies are based on a points-based system with routes for skilled workers, students, family members, and asylum seekers.",
        "source": "UK Government Guide"
    },
    "what is the brexit agreement": {
        "answer": "The Brexit agreement includes the Withdrawal Agreement (2020) and the Trade and Cooperation Agreement (2021) governing the UK-EU relationship.",
        "source": "UK Parliament Guide"
    }
}

class RealRAGEngine:
    def __init__(self, use_openai: bool = False, collect_fresh_data: bool = False):
        self.initialized = True
        self.data_source = "demo"
        logger.info("Lightweight RAG engine initialized (demo mode)")

    def get_data_source(self) -> str:
        return "demo"

    def get_status(self) -> Dict[str, Any]:
        return {"ready": True, "initialized": True, "data_source": "demo"}

    def query(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        question_lower = question.lower().strip()
        for key, answer in DEMO_ANSWERS.items():
            if key in question_lower:
                return {
                    "result": answer["answer"] + f"\n\nSource: {answer['source']}",
                    "source_documents": [],
                    "is_demo_answer": True
                }
        return {
            "result": "I can help with questions about UK Parliament, legislation, MPs, Lords, elections, and parliamentary questions. Please try rephrasing your question.",
            "source_documents": [],
            "is_demo_answer": False
        }

    def add_documents(self, texts: List[str], metadata: List[Dict] = None):
        pass

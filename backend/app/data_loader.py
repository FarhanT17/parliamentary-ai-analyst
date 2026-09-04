import json
import pandas as pd
import requests
from typing import List, Dict, Any
from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ParliamentaryDataLoader:
    """Load and process UK Parliament data from various sources"""
    
    def __init__(self, data_dir: str = "backend/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
    
    def load_hansard_data(self) -> List[Dict[str, Any]]:
        """Load sample Hansard debate data"""
        # Sample data for demo - in production, this would call the API
        sample_data = [
            {
                "id": "debate_001",
                "title": "Prime Minister's Questions",
                "date": "2024-01-15",
                "speaker": "Rishi Sunak",
                "content": "The government is committed to economic growth and lowering inflation. We have made significant progress on the cost of living crisis and are investing in public services. The economy is now in a stronger position than it was a year ago.",
                "house": "Commons",
                "url": "https://hansard.parliament.uk/commons/2024-01-15"
            },
            {
                "id": "debate_002",
                "title": "Budget Statement",
                "date": "2024-03-06",
                "speaker": "Jeremy Hunt",
                "content": "Today I present a budget for long-term growth. We are cutting national insurance, supporting business investment, and taking decisive action to reduce inflation. This is a budget that rewards work and promotes prosperity.",
                "house": "Commons",
                "url": "https://hansard.parliament.uk/commons/2024-03-06"
            },
            {
                "id": "debate_003",
                "title": "Energy Security Debate",
                "date": "2024-02-20",
                "speaker": "Grant Shapps",
                "content": "The UK is a world leader in renewable energy. We are investing in offshore wind, nuclear power, and carbon capture. Our goal is to achieve net zero by 2050 while ensuring energy security for British families.",
                "house": "Commons",
                "url": "https://hansard.parliament.uk/commons/2024-02-20"
            },
            {
                "id": "debate_004",
                "title": "Health and Social Care",
                "date": "2024-04-10",
                "speaker": "Victoria Atkins",
                "content": "The NHS is our priority. We are investing £2.4 billion in modernising hospitals and increasing NHS capacity. We're also expanding the social care workforce to ensure everyone gets the care they deserve.",
                "house": "Commons",
                "url": "https://hansard.parliament.uk/commons/2024-04-10"
            },
            {
                "id": "debate_005",
                "title": "Education Reform",
                "date": "2024-05-02",
                "speaker": "Gillian Keegan",
                "content": "Education is the key to opportunity. We are transforming our education system with new curriculum reforms, investment in teacher training, and a focus on skills for the future economy. Every child deserves a world-class education.",
                "house": "Commons",
                "url": "https://hansard.parliament.uk/commons/2024-05-02"
            },
            {
                "id": "debate_006",
                "title": "Migration and Border Security",
                "date": "2024-06-14",
                "speaker": "James Cleverly",
                "content": "We have a clear plan to stop the boats and secure our borders. The Rwanda partnership is working, and illegal migration has fallen significantly. We are taking back control of our immigration system.",
                "house": "Commons",
                "url": "https://hansard.parliament.uk/commons/2024-06-14"
            },
            {
                "id": "debate_007",
                "title": "Housing and Planning Reform",
                "date": "2024-07-18",
                "speaker": "Michael Gove",
                "content": "We are building the homes Britain needs. Our planning reforms will deliver 1 million new homes, support first-time buyers, and regenerate our town centres. Everyone deserves a secure and affordable home.",
                "house": "Commons",
                "url": "https://hansard.parliament.uk/commons/2024-07-18"
            },
            {
                "id": "debate_008",
                "title": "Climate Change and Net Zero",
                "date": "2024-08-22",
                "speaker": "Claire Coutinho",
                "content": "The UK is committed to achieving net zero by 2050. We are investing £30 billion in green technology, creating high-skilled jobs, and leading the world in clean energy. This is both an environmental and economic opportunity.",
                "house": "Commons",
                "url": "https://hansard.parliament.uk/commons/2024-08-22"
            }
        ]
        return sample_data
    
    def load_legislation_data(self) -> List[Dict[str, Any]]:
        """Load sample legislation data"""
        return [
            {
                "id": "leg_001",
                "title": "Data Protection Act 2018",
                "year": 2018,
                "summary": "The Data Protection Act 2018 is the UK's implementation of the General Data Protection Regulation (GDPR). It governs how personal data is processed and protects individual privacy rights.",
                "url": "https://www.legislation.gov.uk/ukpga/2018/12"
            },
            {
                "id": "leg_002",
                "title": "Climate Change Act 2008",
                "year": 2008,
                "summary": "The Climate Change Act 2008 sets legally binding targets for reducing greenhouse gas emissions. It requires the UK to achieve net zero emissions by 2050.",
                "url": "https://www.legislation.gov.uk/ukpga/2008/27"
            },
            {
                "id": "leg_003",
                "title": "Equality Act 2010",
                "year": 2010,
                "summary": "The Equality Act 2010 consolidates anti-discrimination laws in the UK. It protects people from discrimination based on age, disability, gender reassignment, marriage, race, religion, sex, and sexual orientation.",
                "url": "https://www.legislation.gov.uk/ukpga/2010/15"
            },
            {
                "id": "leg_004",
                "title": "Human Rights Act 1998",
                "year": 1998,
                "summary": "The Human Rights Act 1998 incorporates the European Convention on Human Rights into UK law. It protects fundamental rights including the right to life, freedom of expression, and fair trial.",
                "url": "https://www.legislation.gov.uk/ukpga/1998/42"
            }
        ]
    
    def load_parliamentary_questions(self) -> List[Dict[str, Any]]:
        """Load sample parliamentary questions data"""
        return [
            {
                "id": "pq_001",
                "date": "2024-09-01",
                "mp": "Keir Starmer",
                "department": "Cabinet Office",
                "question": "What steps is the government taking to ensure the UK remains a global leader in artificial intelligence regulation?",
                "answer": "The UK is committed to developing a pro-innovation regulatory framework for AI. We are investing £1.4 billion in the AI sector and have established the AI Safety Institute to lead global research on AI safety.",
                "answer_by": "Cabinet Office"
            },
            {
                "id": "pq_002",
                "date": "2024-09-05",
                "mp": "David Lammy",
                "department": "Foreign Office",
                "question": "What actions are being taken to strengthen diplomatic relations with European partners?",
                "answer": "The UK is rebuilding trust with European partners through the EU-UK Cooperation Agreement on security and law enforcement. We are committed to deepening our partnership on defence, security, and climate change.",
                "answer_by": "Foreign Office"
            },
            {
                "id": "pq_003",
                "date": "2024-09-10",
                "mp": "Rachel Reeves",
                "department": "Treasury",
                "question": "What measures are being implemented to support economic growth and reduce the cost of living?",
                "answer": "The government is implementing a comprehensive growth plan including reducing national insurance, investing in infrastructure, and supporting small businesses. We are also targeting inflation through fiscal discipline.",
                "answer_by": "Treasury"
            }
        ]
    
    def process_hansard_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Process raw Hansard data for vector database"""
        processed = []
        for item in raw_data:
            processed.append({
                "id": item["id"],
                "text": f"Title: {item['title']}\nSpeaker: {item['speaker']}\nContent: {item['content']}",
                "metadata": {
                    "source": "hansard",
                    "title": item["title"],
                    "speaker": item["speaker"],
                    "date": item["date"],
                    "house": item.get("house", "Commons"),
                    "url": item.get("url", "")
                }
            })
        return processed
    
    def process_legislation_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Process raw legislation data for vector database"""
        processed = []
        for item in raw_data:
            processed.append({
                "id": item["id"],
                "text": f"Title: {item['title']}\nSummary: {item['summary']}",
                "metadata": {
                    "source": "legislation",
                    "title": item["title"],
                    "year": item["year"],
                    "url": item.get("url", "")
                }
            })
        return processed
    
    def process_questions_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Process raw parliamentary questions for vector database"""
        processed = []
        for item in raw_data:
            processed.append({
                "id": item["id"],
                "text": f"Question: {item['question']}\nAnswer: {item['answer']}",
                "metadata": {
                    "source": "parliamentary_questions",
                    "mp": item["mp"],
                    "date": item["date"],
                    "department": item["department"],
                    "answer_by": item.get("answer_by", "")
                }
            })
        return processed
    
    def load_all_data(self) -> List[Dict]:
        """Load and process all data sources"""
        all_data = []
        
        # Load Hansard data
        hansard_raw = self.load_hansard_data()
        hansard_processed = self.process_hansard_data(hansard_raw)
        all_data.extend(hansard_processed)
        
        # Load Legislation data
        legislation_raw = self.load_legislation_data()
        legislation_processed = self.process_legislation_data(legislation_raw)
        all_data.extend(legislation_processed)
        
        # Load Parliamentary Questions
        questions_raw = self.load_parliamentary_questions()
        questions_processed = self.process_questions_data(questions_raw)
        all_data.extend(questions_processed)
        
        return all_data
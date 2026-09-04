import logging
from typing import Dict, Any
import os

logger = logging.getLogger(__name__)

class ParliamentaryRAGEngine:
    """RAG engine for parliamentary data"""
    
    def __init__(self):
        self.initialized = False
        self.client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize the RAG engine"""
        try:
            # Try to load OpenAI
            try:
                from openai import OpenAI
                from dotenv import load_dotenv
                load_dotenv()
                
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key and api_key != "your_openai_api_key_here":
                    self.client = OpenAI(api_key=api_key)
                    self.initialized = True
                    logger.info("RAG engine initialized with OpenAI")
                else:
                    logger.warning("No valid OpenAI API key found. Using fallback mode.")
                    self.initialized = False
            except ImportError as e:
                logger.warning(f"OpenAI import error: {e}. Using fallback mode.")
                self.initialized = False
                
        except Exception as e:
            logger.error(f"Failed to initialize RAG engine: {e}")
            self.initialized = False
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        Query the RAG system with a question
        """
        # If not initialized, return a helpful message
        if not self.initialized or not self.client:
            return {
                "result": f"🔍 I understand your question about '{question}'. The full RAG system would search through thousands of parliamentary documents. For this demo, please use the /ask/demo endpoint for immediate answers!",
                "source_documents": []
            }
        
        try:
            # Use OpenAI to generate a response
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant specialized in UK Parliament data. Answer questions clearly and concisely."},
                    {"role": "user", "content": question}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            answer = response.choices[0].message.content
            
            return {
                "result": answer,
                "source_documents": [
                    {"metadata": {"source": "OpenAI - Parliamentary context"}}
                ]
            }
            
        except Exception as e:
            logger.error(f"Error querying RAG engine: {e}")
            return {
                "result": f"I encountered an error. Please try the /ask/demo endpoint instead.",
                "source_documents": []
            }
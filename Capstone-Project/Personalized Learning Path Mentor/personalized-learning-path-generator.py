"""
AI-Powered Personalized Learning Path Generator
A system that creates personalized learning paths using Generative AI capabilities.
"""

import os
import sys
from typing import List, Union, Dict, Any, Optional
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import LangChain components
from langchain.llms import BaseLLM
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.document_loaders import (
    PyPDFLoader,
    TextLoader,
    WebBaseLoader,
    YoutubeLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.agents import AgentType, initialize_agent, Tool
from langchain.memory import ConversationBufferMemory
from langchain.utilities import WikipediaAPIWrapper
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.schema import LLMResult

# Configuration
EMBEDDING_MODEL_NAME = "all-mpnet-base-v2"
VECTORDB_PATH = "chroma_db"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
LLM_TYPE = "gemini"  # Options: "local", "openai", "google", "gemini"

# Get API keys from environment variables
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
KAGGLE_API_KEY = os.getenv("KAGGLE_API_KEY")

class GeminiLLM(BaseLLM):
    """LangChain wrapper for the Gemini API."""
    
    api_key: str
    model_name: str = "gemini-pro"
    
    @property
    def _llm_type(self) -> str:
        return "gemini"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Makes a request to the Gemini API and returns the response."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent",
                headers=headers,
                json=payload,
            )
            
            if response.status_code != 200:
                raise Exception(f"Gemini API error: {response.status_code}, {response.text}")
            
            result = response.json()
            if "candidates" in result and len(result["candidates"]) > 0:
                return result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return "No result found in Gemini response"
                
        except Exception as e:
            raise Exception(f"Error calling Gemini API: {e}")

def load_document(file_path: str) -> List[Any]:
    """Loads a document from a file or URL and returns the text content."""
    try:
        if file_path.startswith(("http://", "https://")):
            if "youtube.com" in file_path:
                loader = YoutubeLoader.from_youtube_url(file_path)
            else:
                loader = WebBaseLoader(file_path)
        elif file_path.lower().endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        else:
            loader = TextLoader(file_path)
            
        data = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )
        return text_splitter.split_documents(data)
    except Exception as e:
        print(f"Error loading document {file_path}: {e}")
        return []

def create_embeddings(model_name: str = EMBEDDING_MODEL_NAME) -> HuggingFaceEmbeddings:
    """Creates and returns a HuggingFaceEmbeddings object."""
    try:
        return HuggingFaceEmbeddings(model_name=model_name)
    except Exception as e:
        print(f"Error creating embeddings: {e}")
        sys.exit(1)

def create_vector_store(
    texts: List[Any],
    embeddings: HuggingFaceEmbeddings,
    db_path: str = VECTORDB_PATH
) -> Chroma:
    """Creates and persists a Chroma vector store."""
    try:
        return Chroma.from_documents(texts, embeddings, persist_directory=db_path)
    except Exception as e:
        print(f"Error creating vector store: {e}")
        sys.exit(1)

def load_vector_store(
    db_path: str = VECTORDB_PATH,
    embeddings: HuggingFaceEmbeddings = None
) -> Chroma:
    """Loads an existing Chroma vector store."""
    try:
        if embeddings is None:
            embeddings = create_embeddings()
        return Chroma(persist_directory=db_path, embedding_function=embeddings)
    except Exception as e:
        print(f"Error loading vector store: {e}")
        sys.exit(1)

def get_similar_docs(query: str, vector_store: Chroma, k: int = 5) -> List[str]:
    """Retrieves the most similar documents from the vector store."""
    try:
        return vector_store.similarity_search(query, k=k)
    except Exception as e:
        print(f"Error retrieving similar documents: {e}")
        return []

def initialize_llm(llm_type: str = LLM_TYPE) -> BaseLLM:
    """Initializes the language model."""
    try:
        if llm_type == "gemini":
            if not GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY must be set for Gemini LLM")
            return GeminiLLM(api_key=GOOGLE_API_KEY)
        elif llm_type == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY must be set for OpenAI LLM")
            from langchain.llms import OpenAI
            return OpenAI(api_key=OPENAI_API_KEY)
        else:
            raise ValueError(f"Unsupported LLM type: {llm_type}")
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        sys.exit(1)

def create_agent(llm: BaseLLM, vector_store: Chroma, memory: ConversationBufferMemory) -> Any:
    """Creates an agent for learning path generation."""
    try:
        tools = [
            Tool(
                name="learning_material_qa",
                func=lambda q: get_similar_docs(q, vector_store),
                description="Useful for answering questions about learning materials.",
            ),
            WikipediaAPIWrapper(),
        ]
        return initialize_agent(
            tools,
            llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            memory=memory,
            verbose=True,
        )
    except Exception as e:
        print(f"Error creating agent: {e}")
        sys.exit(1)

def create_learning_path(agent: Any, learning_goal: str, user_knowledge: str = "") -> str:
    """Creates a personalized learning path."""
    try:
        prompt = f"""
        Create a personalized learning path for the following goal: {learning_goal}
        """
        if user_knowledge:
            prompt += f"\nUser's current knowledge level: {user_knowledge}"
        prompt += """
        The learning path should include:
        1. Clear learning objectives
        2. Recommended resources
        3. Assessment methods
        4. Timeline estimates
        Format the output in a clear, structured way.
        """
        return agent.run(prompt)
    except Exception as e:
        print(f"Error creating learning path: {e}")
        return "Sorry, I could not create a learning path."

def main():
    """Main function to orchestrate the learning path generation."""
    try:
        # Create data directory if it doesn't exist
        if not os.path.exists("data"):
            os.makedirs("data")
            
        # Sample learning materials
        document_paths = [
            "data/example1.txt",
            "data/example2.txt",
            "data/generative_ai_overview.txt"
        ]
        
        # Create sample files if they don't exist
        if not os.path.exists("data/example1.txt"):
            with open("data/example1.txt", "w") as f:
                f.write("Python programming basics including variables, loops, and functions.")
                
        if not os.path.exists("data/example2.txt"):
            with open("data/example2.txt", "w") as f:
                f.write("Introduction to data structures and algorithms.")
                
        if not os.path.exists("data/generative_ai_overview.txt"):
            with open("data/generative_ai_overview.txt", "w") as f:
                f.write("""
                Generative AI Overview:
                - GANs (Generative Adversarial Networks)
                - VAEs (Variational Autoencoders)
                - Diffusion Models
                - Large Language Models (LLMs)
                """)
        
        # Load and process documents
        documents = []
        for doc_path in document_paths:
            docs = load_document(doc_path)
            if docs:
                documents.extend(docs)
                print(f"Loaded document: {doc_path}")
        
        if not documents:
            print("No documents loaded. Exiting.")
            sys.exit(1)
        
        # Create embeddings and vector store
        embeddings = create_embeddings()
        if os.path.exists(VECTORDB_PATH):
            print("Loading existing vector store...")
            vector_store = load_vector_store(VECTORDB_PATH, embeddings)
        else:
            print("Creating new vector store...")
            vector_store = create_vector_store(documents, embeddings)
            vector_store.persist()
        
        # Initialize LLM and agent
        llm = initialize_llm()
        memory = ConversationBufferMemory(memory_key="chat_history", input_key="input")
        agent = create_agent(llm, vector_store, memory)
        
        # Get user input and create learning path
        learning_goal = input("Enter your learning goal: ")
        user_knowledge = input("Enter your current knowledge level (beginner/intermediate/advanced): ")
        
        print("\nGenerating your personalized learning path...\n")
        learning_path = create_learning_path(agent, learning_goal, user_knowledge)
        print("\nYour Personalized Learning Path:\n")
        print(learning_path)
        
        # Interactive Q&A
        print("\nYou can now ask questions about your learning path. Type 'exit' to quit.")
        while True:
            query = input("\nYour question: ")
            if query.lower() == 'exit':
                break
            try:
                response = agent.run(query)
                print(f"\n{response}")
            except Exception as e:
                print(f"Error: {e}")
                
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)
    finally:
        print("\nThank you for using the AI-Powered Learning Path Generator!")

if __name__ == "__main__":
    main()


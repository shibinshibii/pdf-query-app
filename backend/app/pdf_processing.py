# Import necessary modules and classes
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core.prompts import PromptTemplate
import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# Function to create an index for a given PDF file
def create_index_for_pdf(file_path):
    # Check if the file exists and is not empty
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise Exception(f"Invalid or empty file: {file_path}")
    
    # Ensure the file has a .pdf extension
    if not file_path.lower().endswith('.pdf'):
        raise Exception("Only PDF files are supported.")
    
    try:
        # Load the PDF file as documents using SimpleDirectoryReader
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
    except Exception as e:
        # Handle errors during document loading
        raise Exception(f"Failed to load PDF: {str(e)}")
    
    try:
        # Configure the embedding model using GeminiEmbedding
        Settings.embed_model = GeminiEmbedding(
            model_name="models/embedding-001",  # Specify the model name
            api_key=os.getenv("GOOGLE_API_KEY")  # Retrieve API key from environment variables
        )
        # Create a vector store index from the loaded documents
        index = VectorStoreIndex.from_documents(documents)
    except Exception as e:
        # Handle errors during index creation
        raise Exception(f"Failed to create index: {str(e)}")
    
    # Define the path to save the index
    index_path = os.path.join("indexes", os.path.basename(file_path))
    try:
        # Create the directory for saving the index if it doesn't exist
        os.makedirs(index_path, exist_ok=True)
        # Persist the index to the specified directory
        index.storage_context.persist(persist_dir=index_path)
        # Verify that the index was saved successfully
        if not os.path.exists(os.path.join(index_path, "docstore.json")):
            raise Exception(f"Index not saved: {index_path}/docstore.json missing")
    except Exception as e:
        # Handle errors during index saving
        raise Exception(f"Failed to save index: {str(e)}")

# Function to extract text content from a PDF file
def extract_text_from_pdf(file_path):
    try:
        # Load the PDF file as documents
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        # Concatenate the text content of all documents and return it
        return " ".join([doc.text for doc in documents])
    except Exception as e:
        # Handle errors during text extraction
        raise Exception(f"Failed to extract text: {str(e)}")

# Function to initialize the Gemini LLM (Language Learning Model)
def initialize_llm():
    try:
        # Define a prompt template for question answering
        qa_prompt = PromptTemplate(
            "Instruction: Answer the question based on the provided context.\n"
            "Context: {context_str}\n"
            "Question: {query_str}\n"
            "Answer: "
        )
        # Configure the Gemini LLM with specific parameters
        llm = Gemini(
            model_name="models/gemini-1.5-flash",  # Specify the model name
            api_key=os.getenv("GOOGLE_API_KEY"),  # Retrieve API key from environment variables
            temperature=0.5,  # Set the temperature for response variability
            max_tokens=256,  # Limit the maximum number of tokens in the response
        )
        # Set the LLM and prompt template in the global settings
        Settings.llm = llm
        Settings.text_qa_template = qa_prompt
    except Exception as e:
        # Handle errors during LLM initialization
        raise Exception(f"Failed to initialize Gemini: {str(e)}")

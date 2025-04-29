PDF Query App
A full-stack web application for uploading PDF documents and asking questions about their content using AI. Built with a FastAPI backend, React frontend, and powered by Google Gemini for natural language processing, this app allows users to upload PDFs, index their content, and query them interactively with a chat-like interface.
Features

PDF Upload: Upload PDF files, which are indexed for querying.
Question Answering: Ask questions about the PDF content, powered by Gemini 1.5 Flash.
Chat Interface: Displays question-answer history with a loading state and error toasts.
Persistent Storage: Stores PDFs, indices, and metadata in SQLite.
Responsive UI: Built with React.

Tech Stack

Frontend: React, Axios
Backend: FastAPI, LlamaIndex, Gemini API (gemini-1.5-flash, embedding-001)
Database: SQLite
Deployment: Vercel (frontend), Render (backend)
Other: Python, SQLAlchemy

Prerequisites

Node.js (v16+): For frontend development.
Python (3.9+): For backend development.
Git: For version control.
Google Gemini API Key: Obtain from Google AI Studio.

Setup Instructions

Clone the Repository:
git clone https://github.com/shibinshibii/pdf-query-app.git
cd pdf-query-app


Backend Setup:

Navigate to the backend directory:cd backend


Create a virtual environment and install dependencies:python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt


Create a .env file in backend/:GOOGLE_API_KEY=your_api_key
DATABASE_URL=sqlite:///./pdf_documents.db


Run the FastAPI server:uvicorn main:app --reload


Backend runs at http://127.0.0.1:8000.


Frontend Setup:

Navigate to the frontend directory:cd frontend


Install dependencies:npm install


Create a .env file in frontend/:VITE_API_URL=http://127.0.0.1:8000


Run the React app:npm start


Frontend runs at http://localhost:5173.




Usage

Upload a PDF:
Navigate to the frontend 
Upload a PDF file (e.g., Frontend Developer Task Sheet.pdf).
Wait for the upload to complete (loading state shown).


Ask Questions:
Enter a question (e.g., “What is this PDF about?”).
View the answer in the chat history, with toasts for errors.


Clear Chat:
Click the trash icon to clear chat history.




Limitations:

Render Spin-Down: Backend may take ~30 seconds to wake up after inactivity. The frontend’s loading state (⏳ Loading...) mitigates this.
Gemini API: Limited to 15 requests/minute (free tier). Monitor in Google AI Studio.
Storage: Render’s free tier provides 1 GB for PDFs and indices.



Contributing

Fork the repository.
Create a feature branch (git checkout -b feature/your-feature).
Commit changes (git commit -m "Add your feature").
Push to the branch (git push origin feature/your-feature).
Open a pull request.

License
MIT License. See LICENSE for details.
Acknowledgments

Built for the AI Planet Frontend Developer Task.
Powered by Google Gemini and LlamaIndex.


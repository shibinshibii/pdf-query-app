import "../styles/askquestion.css";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { FiSend } from "react-icons/fi";
import React, { useState, useEffect, useRef } from "react";
import { FaUserCircle } from "react-icons/fa"; // User icon
import { GiArtificialIntelligence } from "react-icons/gi"; // AI Icon
import { FaTrashAlt } from 'react-icons/fa';
import api from "../api";

function AskQuestion({ uploadedFileName }) {
  const [question, setQuestion] = useState("");   // State to store the user's question
  const [chatHistory, setChatHistory] = useState([]);   // State to store the chat history (array of question-answer pairs)
  const endOfChatRef = useRef(null); // Reference to scroll to the last message
  
  // Load chat history when component mounts or filename changes
  useEffect(() => {
    if (uploadedFileName) {
      try {
        const savedChat = localStorage.getItem(`chatHistory_${uploadedFileName}`);
        if (savedChat) {
          setChatHistory(JSON.parse(savedChat));
        } else {
          setChatHistory([]);  // Reset when switching to a new file
        }
      } catch (error) {
        console.error("Error loading chat history:", error);
        setChatHistory([]);
      }
    }
  }, [uploadedFileName]);

  // Save chat history whenever it changes
  useEffect(() => {
    if (uploadedFileName && chatHistory.length > 0) {
      try {
        localStorage.setItem(`chatHistory_${uploadedFileName}`, JSON.stringify(chatHistory));
      } catch (error) {
        console.error("Error saving chat history:", error);
        toast.error("Failed to save chat history");
      }
    }
    
    // Scroll to the end of chat
    if (endOfChatRef.current) {
      endOfChatRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatHistory, uploadedFileName]);

  const handleAsk = async () => {
    if (!question.trim()) {
      toast.error("Question cannot be empty");
      return;
    }
    if (!uploadedFileName) {
      toast.error("No file uploaded");
      return;
    }
    const currentQuestion = question; // Store the current question
    setQuestion(""); // Clear the input field

    setChatHistory((prevHistory) => [
      ...prevHistory,
      { question: currentQuestion, answer: null },
    ]);   // Add the question to chat history with a placeholder for the answer

    const payload = { filename: uploadedFileName, question: currentQuestion }; // Prepare the payload for the API request

    try {
      const response = await api.post("/ask/", payload); // Send the question to the backend API
      const answer = response.data.answer; // Extract the answer from the response
    
      // Update the chat history with the received answer
      setChatHistory((prevHistory) => {
        const updatedHistory = [...prevHistory];
        updatedHistory[updatedHistory.length - 1].answer = answer; // Add the answer to the last question
        return updatedHistory;
      });
    } catch (error) {
      console.error("Error asking question:", error);
      const errorMsg = error.response?.data?.detail || "Request failed";
      toast.error(errorMsg); // Show error toast

      // Update the chat history with the error message
      setChatHistory((prevHistory) => {
        const updatedHistory = [...prevHistory];
        updatedHistory[updatedHistory.length - 1].answer = <i>No Response</i>;
        return updatedHistory;
      });
    }
  };

  // For clearing chat
  const handleClearChat = () => {
    setChatHistory([]);
    localStorage.removeItem(`chatHistory_${uploadedFileName}`);
  };

  // Handle Enter key press to submit questions
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  return (
    <div className="ask-container">
      {/* Render the chat history */}
      {chatHistory.map((chat, index) => (
        <div className="chat-container" key={index}>
          <div className="question-container">
            <FaUserCircle style={{ fontSize: "35px" }} />
            <div className="question">{chat.question}</div>
          </div>
          <div className="answer-container">
            <GiArtificialIntelligence style={{ fontSize: "35px" }} />
            <div className="answer">
              {chat.answer === null ? (
                <span className="loader">Loading...</span> // Placeholder while waiting for the answer
              ) : (
                chat.answer // Display the answer
              )}
            </div>
          </div>
        </div>
      ))}

      {/* Empty div for auto-scrolling */}
      <div ref={endOfChatRef} style={{ paddingBottom: "50px" }}></div>
      
      {/* Input field and send button */}
      <div className="input-container">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyPress={handleKeyPress}
          className="input"
          placeholder="Type a message"
        />
        <button 
          title="Clear chat" 
          className="delete-btn" 
          onClick={handleClearChat}
        >
          <FaTrashAlt/>
        </button>
        <button
          onClick={handleAsk}
          disabled={!uploadedFileName}
          className="send-btn"
        >
          <FiSend />
        </button>
      </div>

      {/* Toast container for notifications */}
      <ToastContainer position="bottom-right" autoClose={3000} />
    </div>
  );
}

export default AskQuestion;
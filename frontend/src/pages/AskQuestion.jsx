import "../styles/askquestion.css";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { FiSend, FiFileText, FiCpu, FiInfo, FiChevronDown, FiChevronUp } from "react-icons/fi";
import React, { useState, useEffect, useRef } from "react";
import { FaUserCircle, FaRobot, FaTrashAlt } from "react-icons/fa";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from 'react-markdown';
import api from "../api";

// Simple Session ID generator (Guest Session)
const getSessionId = () => {
  let sessionId = localStorage.getItem("guest_session_id");
  if (!sessionId) {
    // Fallback to random string if crypto.randomUUID is not available
    sessionId = typeof crypto.randomUUID === 'function' 
      ? crypto.randomUUID() 
      : Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    localStorage.setItem("guest_session_id", sessionId);
  }
  return sessionId;
};

function AskQuestion({ uploadedFileName }) {
  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [expandedSources, setExpandedSources] = useState({}); // Track which message sources are expanded
  const endOfChatRef = useRef(null);
  const sessionId = getSessionId();
  
  // Load chat history from BACKEND
  useEffect(() => {
    const fetchHistory = async () => {
      if (uploadedFileName) {
        try {
          const response = await api.get(`/history/${uploadedFileName}`, {
            params: { session_id: sessionId }
          });
          setChatHistory(response.data);
        } catch (error) {
          console.error("Error loading chat history:", error);
          toast.error("Failed to load chat history");
        }
      } else {
        setChatHistory([]);
      }
    };
    
    fetchHistory();
  }, [uploadedFileName, sessionId]);

  useEffect(() => {
    if (endOfChatRef.current) {
      endOfChatRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatHistory]);

  const toggleSources = (index) => {
    setExpandedSources(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    if (!uploadedFileName) {
      toast.error("Please upload a PDF first");
      return;
    }

    const currentQuestion = question;
    setQuestion("");

    // Add user message to UI immediately
    setChatHistory((prevHistory) => [
      ...prevHistory,
      { question: currentQuestion, answer: null, sources: [] },
    ]);

    try {
      const response = await api.post("/ask/", { 
        filename: uploadedFileName, 
        question: currentQuestion,
        session_id: sessionId
      });
      
      setChatHistory((prevHistory) => {
        const updatedHistory = [...prevHistory];
        const lastIndex = updatedHistory.length - 1;
        updatedHistory[lastIndex].answer = response.data.answer;
        updatedHistory[lastIndex].sources = response.data.sources || [];
        return updatedHistory;
      });
    } catch (error) {
      console.error("Error asking question:", error);
      const errorMsg = error.response?.data?.detail || "AI failed to respond";
      toast.error(errorMsg);

      setChatHistory((prevHistory) => {
        const updatedHistory = [...prevHistory];
        updatedHistory[updatedHistory.length - 1].answer = (
          <span className="text-danger">Sorry, I encountered an error. Please try again.</span>
        );
        return updatedHistory;
      });
    }
  };

  const handleClearChat = async () => {
    try {
      await api.delete(`/history/${uploadedFileName}`, {
        params: { session_id: sessionId }
      });
      setChatHistory([]);
      setShowClearConfirm(false);
      toast.success("Chat history cleared");
    } catch (error) {
      console.error("Error clearing history:", error);
      toast.error("Failed to clear history");
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  return (
    <div className="ask-container">
      <div className="chat-main">
        <AnimatePresence mode="wait">
          {!uploadedFileName ? (
            <motion.div 
              key="no-file"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="empty-state-card"
            >
              <div className="icon-circle">
                <FiFileText size={40} />
              </div>
              <h2>Ready to analyze</h2>
              <p>Upload a PDF document to start an interactive conversation with AI about its content.</p>
            </motion.div>
          ) : chatHistory.length === 0 ? (
            <motion.div 
              key="empty-chat"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="empty-state-card"
            >
              <div className="icon-circle ai">
                <FiCpu size={40} />
              </div>
              <h2>PDF Indexed Successfully</h2>
              <p>The document is ready. Ask me anything! For example: "What are the key takeaways?"</p>
            </motion.div>
          ) : (
            <div className="messages-list">
              {chatHistory.map((chat, index) => (
                <div key={index} className="message-group">
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="message-row user"
                  >
                    <div className="bubble user">
                      {chat.question}
                    </div>
                    <div className="avatar user">
                      <FaUserCircle />
                    </div>
                  </motion.div>

                  <motion.div 
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 }}
                    className="message-row ai"
                  >
                    <div className="avatar ai">
                      <FaRobot />
                    </div>
                    <div className="bubble ai">
                      {chat.answer === null ? (
                        <div className="ai-loading">
                          <span className="dot"></span>
                          <span className="dot"></span>
                          <span className="dot"></span>
                        </div>
                      ) : (
                        <>
                          <div className="ai-text">
                            {typeof chat.answer === 'string' ? (
                              <ReactMarkdown>{chat.answer}</ReactMarkdown>
                            ) : (
                              chat.answer
                            )}
                          </div>
                          
                          {chat.sources && chat.sources.length > 0 && (
                            <div className="sources-container">
                              <button 
                                className="sources-toggle"
                                onClick={() => toggleSources(index)}
                              >
                                <FiInfo size={14} />
                                <span>{chat.sources.length} Source{chat.sources.length > 1 ? 's' : ''}</span>
                                {expandedSources[index] ? <FiChevronUp /> : <FiChevronDown />}
                              </button>
                              
                              <AnimatePresence>
                                {expandedSources[index] && (
                                  <motion.div 
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: 'auto', opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    className="sources-list"
                                  >
                                    {chat.sources.map((source, sIdx) => (
                                      <div key={sIdx} className="source-item">
                                        <span className="source-page">Page {source.page}</span>
                                        <p className="source-text">"{source.text}"</p>
                                      </div>
                                    ))}
                                  </motion.div>
                                )}
                              </AnimatePresence>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </motion.div>
                </div>
              ))}
              <div ref={endOfChatRef} />
            </div>
          )}
        </AnimatePresence>
      </div>
      
      <div className="input-wrapper">
        <div className="input-box glass">
          <textarea
            rows="1"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={uploadedFileName ? "Message PDF Reviewer..." : "Upload a PDF to start chatting"}
            disabled={!uploadedFileName}
          />
          
          <div className="actions">
            <AnimatePresence mode="wait">
              {showClearConfirm ? (
                <motion.div 
                  key="confirm"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="clear-confirm-pill"
                >
                  <span onClick={handleClearChat} className="confirm-yes">Clear?</span>
                  <span onClick={() => setShowClearConfirm(false)} className="confirm-no">No</span>
                </motion.div>
              ) : (
                <motion.button 
                  key="trash"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="icon-btn delete" 
                  onClick={() => setShowClearConfirm(true)}
                  disabled={chatHistory.length === 0}
                  title="Clear Conversation"
                >
                  <FaTrashAlt />
                </motion.button>
              )}
            </AnimatePresence>
            <button
              className="send-btn-round"
              onClick={handleAsk}
              disabled={!uploadedFileName || !question.trim()}
              title="Send Message"
            >
              <FiSend />
            </button>
          </div>
        </div>
      </div>

      <ToastContainer theme="colored" position="bottom-right" autoClose={3000} />
    </div>
  );
}

export default AskQuestion;
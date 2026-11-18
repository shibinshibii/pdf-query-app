import "../styles/askquestion.css";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { FiSend, FiFileText, FiChevronDown, FiChevronUp, FiUploadCloud, FiDownload } from "react-icons/fi";
import React, { useState, useEffect, useRef } from "react";
import { FaUserCircle, FaRobot, FaTrashAlt } from "react-icons/fa";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from 'react-markdown';
import api, { API_BASE_URL } from "../api";

// Visual Source Card with Progressive Hydration from Go Preprocessor
const VisualSourceCard = ({ source, onPreviewDoc }) => {
  const [loading, setLoading] = useState(source.status === 'pending');
  const [snippetUrl, setSnippetUrl] = useState(source.snippet_url || null);
  const [status, setStatus] = useState(source.status || 'pending');
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    if (source.status === 'pending' && source.fetch_url && !snippetUrl) {
      let isMounted = true;
      const url = source.fetch_url.startsWith('http') 
        ? source.fetch_url 
        : `${API_BASE_URL}${source.fetch_url}`;

      api.get(url, { timeout: 15000 })
        .then(res => {
          if (!isMounted) return;
          if (res.data && res.data.status === 'ready' && res.data.snippet_url) {
            setSnippetUrl(res.data.snippet_url);
            setStatus('ready');
            setLoading(false);
          } else if (res.data && res.data.status === 'not_found') {
            setStatus('not_found');
            setLoading(false);
          } else {
            setLoading(false);
          }
        })
        .catch(err => {
          console.warn('[Go Snippet Hydration]', err);
          if (isMounted) setLoading(false);
        });

      return () => { isMounted = false; };
    }
  }, [source.fetch_url, source.status, snippetUrl]);

  if (status === 'not_found') {
    return null;
  }

  const resolvedUrl = snippetUrl 
    ? (snippetUrl.startsWith('http') ? snippetUrl : `${API_BASE_URL}${snippetUrl}`)
    : null;

  const docName = source.document || source.filename || "Document";

  return (
    <div className="source-item">
      <div className="source-header d-flex align-items-center justify-content-between">
        <div className="d-flex align-items-center gap-2">
          <span 
            className="source-doc-badge preview-link" 
            onClick={() => onPreviewDoc && onPreviewDoc({ filename: source.filename, original_name: docName })}
            title={`Preview ${docName}`}
          >
            <FiFileText /> {docName}
          </span>
          <span className="source-page">Page {source.page}</span>
        </div>

        {loading ? (
          <span className="source-loading-badge">
            <span className="source-pulse-dot"></span> Loading snapshot...
          </span>
        ) : resolvedUrl && !loadError ? (
          <span className="source-hint">Click image to enlarge</span>
        ) : null}
      </div>

      <div className="source-body">
        {loading ? (
          <div className="source-skeleton-container">
            <div className="source-skeleton-bar shimmer"></div>
            <div className="source-skeleton-bar short shimmer"></div>
          </div>
        ) : resolvedUrl && !loadError ? (
          <div className="source-snippet-wrapper">
            <a 
              href={resolvedUrl} 
              target="_blank" 
              rel="noopener noreferrer" 
              title={`View snapshot from ${docName} (Page ${source.page})`}
              className="source-snippet-link"
            >
              <img 
                src={resolvedUrl} 
                alt={`Referenced area from ${docName} Page ${source.page}`} 
                className="source-snippet-img"
                loading="lazy"
                onError={() => setLoadError(true)}
              />
            </a>
          </div>
        ) : (
          <p className="source-text">"{source.text}"</p>
        )}
      </div>
    </div>
  );
};

function AskQuestion({
  chatId,
  documents = [],
  messages = [],
  onUploadFile,
  onSendMessage,
  onClearChat,
  onPreviewFile,
  isAsking = false
}) {
  const [question, setQuestion] = useState("");
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [expandedSources, setExpandedSources] = useState({});
  const endOfChatRef = useRef(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (endOfChatRef.current) {
      endOfChatRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isAsking]);

  const handleExportChat = () => {
    const answered = messages.filter((m) => m.question);
    const lines = [
      "# Chat Export",
      "",
      `Exported: ${new Date().toLocaleString()}`,
      ""
    ];
    if (documents.length > 0) {
      lines.push(
        `Documents: ${documents.map((d) => d.original_name || d.filename).join(", ")}`,
        ""
      );
    }
    answered.forEach((m, i) => {
      lines.push(`### Question ${i + 1}`, "", m.question, "");
      lines.push("### Answer", "", m.answer || "_No answer._", "");
      if (m.sources && m.sources.length > 0) {
        lines.push("**Sources:**", "");
        m.sources.forEach((s) => {
          lines.push(`- ${s.document || s.filename || "Document"}, page ${s.page}`);
        });
        lines.push("");
      }
      lines.push("---", "");
    });
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chat-${chatId || "session"}-export.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  // Auto-grow the textarea with its content (capped by CSS max-height)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [question]);

  const toggleSources = (index) => {
    setExpandedSources(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const handleSend = () => {
    if (!question.trim() || isAsking) return;
    if (documents.length === 0) {
      toast.error("Please upload a PDF first");
      return;
    }
    const q = question;
    setQuestion("");
    onSendMessage(q);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      onUploadFile(file);
      e.target.value = "";
    }
  };

  return (
    <div className="ask-container">
      <ToastContainer position="top-right" autoClose={3000} theme="colored" />

      <input
        type="file"
        accept="application/pdf"
        ref={fileInputRef}
        style={{ display: "none" }}
        onChange={handleFileChange}
      />

      <div className="chat-main">
        {documents.length === 0 ? (
          <div className="empty-state-card animate-fade-in">
            <div className="icon-circle">
              <FiUploadCloud size={44} />
            </div>
            <h2>Chat with Your PDF Documents</h2>
            <p>Upload your PDF files to ask questions and see exact page snapshots for every answer.</p>
            <button
              className="btn btn-primary mt-3 d-flex align-items-center gap-2 px-4 py-2"
              onClick={() => fileInputRef.current?.click()}
            >
              <FiUploadCloud />
              <span>Upload PDF</span>
            </button>
          </div>
        ) : messages.length === 0 ? (
          <div className="empty-state-card animate-fade-in">
            <div className="icon-circle ai">
              <FaRobot size={44} />
            </div>
            <h2>Ready to Answer</h2>
            <p>
              I have <strong>{documents.length} document{documents.length > 1 ? "s" : ""}</strong> ready. Ask any question below!
            </p>
          </div>
        ) : (
          <div className="messages-list">
            {messages.map((item, index) => {
              const isSourcesExpanded = !!expandedSources[index];
              return (
                <div key={item.id || index} className="message-group animate-fade-in">
                  {/* User Question */}
                  <div className="message-row user">
                    <div className="bubble user">
                      <p>{item.question}</p>
                    </div>
                    <div className="avatar user">
                      <FaUserCircle />
                    </div>
                  </div>

                  {/* AI Answer */}
                  <div className="message-row ai">
                    <div className="avatar ai">
                      <FaRobot />
                    </div>
                    <div className="bubble ai">
                      {item.answer ? (
                        <div className="markdown-content">
                          <ReactMarkdown>{item.answer}</ReactMarkdown>
                        </div>
                      ) : (
                        <div className="ai-loading">
                          <div className="dot"></div>
                          <div className="dot"></div>
                          <div className="dot"></div>
                        </div>
                      )}

                      {/* Source Citations with Multi-Doc Attribution */}
                      {item.sources && item.sources.length > 0 && (
                        <div className="sources-container">
                          <div
                            className="sources-toggle"
                            onClick={() => toggleSources(index)}
                          >
                            <div className="sources-title d-flex align-items-center gap-1">
                              <FiFileText className="sources-icon" />
                              <span>View Sources ({item.sources.length})</span>
                            </div>
                            {isSourcesExpanded ? <FiChevronUp /> : <FiChevronDown />}
                          </div>

                          <AnimatePresence>
                            {isSourcesExpanded && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                transition={{ duration: 0.2 }}
                                className="sources-content"
                              >
                                {item.sources.map((source, sIdx) => (
                                  <VisualSourceCard
                                    key={`${source.filename || source.document}_${source.page}_${sIdx}`}
                                    source={source}
                                    onPreviewDoc={onPreviewFile}
                                  />
                                ))}
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={endOfChatRef} />
          </div>
        )}
      </div>

      {/* Floating Bottom Input Bar */}
      <div className="input-wrapper">
        <div className="input-box">
          {/* Clear Chat Confirmation or Button */}
          <div className="actions">
            <AnimatePresence mode="wait">
              {showClearConfirm ? (
                <motion.div
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.8, opacity: 0 }}
                  className="clear-confirm-pill"
                >
                  <span>Clear?</span>
                  <span
                    className="confirm-yes"
                    onClick={() => {
                      onClearChat();
                      setShowClearConfirm(false);
                    }}
                  >
                    Yes
                  </span>
                  <span>|</span>
                  <span
                    className="confirm-no"
                    onClick={() => setShowClearConfirm(false)}
                  >
                    No
                  </span>
                </motion.div>
              ) : (
                <>
                <button
                  className="icon-btn export"
                  title="Export conversation to Markdown"
                  disabled={messages.length === 0}
                  onClick={handleExportChat}
                >
                  <FiDownload />
                </button>
                <button
                  className="icon-btn delete"
                  title="Clear conversation"
                  disabled={messages.length === 0}
                  onClick={() => setShowClearConfirm(true)}
                >
                  <FaTrashAlt />
                </button>
                </>
              )}
            </AnimatePresence>
          </div>

          <textarea
            ref={textareaRef}
            rows="1"
            placeholder={
              documents.length === 0
                ? "Upload a PDF above to start chatting..."
                : "Ask anything about your uploaded documents..."
            }
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isAsking || documents.length === 0}
          />

          <button
            className="send-btn-round"
            onClick={handleSend}
            disabled={!question.trim() || isAsking || documents.length === 0}
            title="Send Question"
          >
            <FiSend />
          </button>
        </div>
      </div>
    </div>
  );
}

export default AskQuestion;

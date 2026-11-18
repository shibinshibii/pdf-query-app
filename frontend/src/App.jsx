import React, { useState, useEffect, useCallback, useRef } from "react";
import NavBar from "./pages/NavBar";
import AskQuestion from "./pages/AskQuestion";
import PreviewModal from "./components/PreviewModal";
import api, { API_BASE_URL } from "./api";
import { toast } from "react-toastify";
import { motion, AnimatePresence } from "framer-motion";
import { FiUploadCloud } from "react-icons/fi";
import "./styles/dropoverlay.css";

function App() {
  const [chatId, setChatId] = useState(() => {
    return localStorage.getItem("current_chat_id") || "";
  });
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // Initialize or fetch the active chat session
  const initChat = useCallback(async (existingId) => {
    try {
      if (existingId) {
        const res = await api.get(`/api/chats/${existingId}`);
        setChatId(res.data.id);
        setDocuments(res.data.documents || []);
        setMessages(res.data.messages || []);
        return res.data;
      }
    } catch (err) {
      console.warn("Could not resume previous chat, creating fresh session:", err);
    }

    // Create fresh session if none exists or previous was not found
    try {
      const res = await api.post("/api/chats/", { title: "Document Review" });
      setChatId(res.data.id);
      setDocuments([]);
      setMessages([]);
      localStorage.setItem("current_chat_id", res.data.id);
      return res.data;
    } catch (err) {
      console.error("Failed to initialize chat session:", err);
    }
  }, []);

  useEffect(() => {
    initChat(chatId);
  }, []);

  // Poll chat details while any document is in "indexing" status
  useEffect(() => {
    if (!chatId) return;
    const hasIndexing = documents.some((d) => d.status === "indexing");
    if (!hasIndexing) return;

    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/chats/${chatId}`);
        setDocuments(res.data.documents || []);
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [chatId, documents]);

  // Upload PDF document to current session
  const handleUploadFile = async (file) => {
    let targetChatId = chatId;
    if (!targetChatId) {
      const newChat = await initChat();
      targetChatId = newChat.id;
    }

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);
    try {
      await api.post(`/api/chats/${targetChatId}/documents`, formData);
      toast.info(`Uploaded "${file.name}". Preparing document...`);

      // Refresh documents
      const res = await api.get(`/api/chats/${targetChatId}`);
      setDocuments(res.data.documents || []);
    } catch (err) {
      console.error("Upload error:", err);
      const detail = err.response?.data?.detail || "Upload failed";
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  // Keep a ref to the latest upload handler so window listeners never go stale
  const uploadRef = useRef(handleUploadFile);
  uploadRef.current = handleUploadFile;

  // Full-window drag-and-drop for PDF files
  useEffect(() => {
    let dragDepth = 0;
    const hasFiles = (e) => Array.from(e.dataTransfer?.types || []).includes("Files");

    const onDragEnter = (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      dragDepth += 1;
      setIsDragging(true);
    };
    const onDragOver = (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
    };
    const onDragLeave = (e) => {
      if (!hasFiles(e)) return;
      dragDepth = Math.max(0, dragDepth - 1);
      if (dragDepth === 0) setIsDragging(false);
    };
    const onDrop = (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      dragDepth = 0;
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files || []);
      const pdfs = files.filter(
        (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf")
      );
      if (pdfs.length === 0) {
        toast.error("Only PDF files can be uploaded");
        return;
      }
      pdfs.forEach((file) => uploadRef.current(file));
    };

    window.addEventListener("dragenter", onDragEnter);
    window.addEventListener("dragover", onDragOver);
    window.addEventListener("dragleave", onDragLeave);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragenter", onDragEnter);
      window.removeEventListener("dragover", onDragOver);
      window.removeEventListener("dragleave", onDragLeave);
      window.removeEventListener("drop", onDrop);
    };
  }, []);

  // Remove a document from the current session
  const handleRemoveFile = async (docId) => {
    if (!chatId) return;
    try {
      await api.delete(`/api/chats/${chatId}/documents/${docId}`);
      toast.success("Document removed");

      // Refresh documents
      const res = await api.get(`/api/chats/${chatId}`);
      setDocuments(res.data.documents || []);
    } catch (err) {
      console.error("Remove file error:", err);
      toast.error("Failed to remove document");
    }
  };

  // Clear current chat session / conversation
  const handleClearChat = async () => {
    if (!chatId) return;
    try {
      // Create a fresh chat session and clean up
      await api.delete(`/api/chats/${chatId}`);
      toast.success("Conversation cleared");
      await initChat();
    } catch (err) {
      console.error("Clear chat error:", err);
      // Fallback: reset state
      setMessages([]);
      await initChat();
    }
  };

  // Send question to AI
  const handleSendMessage = async (questionText) => {
    if (!chatId || isAsking) return;

    // Optimistically append user question
    const tempUserMsg = {
      question: questionText,
      answer: null,
      sources: []
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setIsAsking(true);

    try {
      const res = await api.post(`/api/chats/${chatId}/ask`, {
        question: questionText
      });

      setMessages((prev) => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        updated[lastIdx] = {
          ...updated[lastIdx],
          answer: res.data.answer,
          sources: res.data.sources || []
        };
        return updated;
      });
    } catch (err) {
      console.error("Ask question error:", err);
      const detail = err.response?.data?.detail || "AI failed to respond";
      toast.error(detail);

      setMessages((prev) => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        updated[lastIdx] = {
          ...updated[lastIdx],
          answer: `⚠️ Error: ${detail}`
        };
        return updated;
      });
    } finally {
      setIsAsking(false);
    }
  };

  // Preview PDF in modal
  const handlePreviewFile = (doc) => {
    if (!doc || !doc.filename) return;
    setPreviewFile({
      url: `${API_BASE_URL}/uploads/${doc.filename}`,
      name: doc.original_name || doc.filename
    });
  };

  return (
    <>
      <NavBar
        documents={documents}
        loading={loading}
        onUploadFile={handleUploadFile}
        onRemoveFile={handleRemoveFile}
        onPreviewFile={handlePreviewFile}
      />

      <AskQuestion
        chatId={chatId}
        documents={documents}
        messages={messages}
        onUploadFile={handleUploadFile}
        onSendMessage={handleSendMessage}
        onClearChat={handleClearChat}
        onPreviewFile={handlePreviewFile}
        isAsking={isAsking}
      />

      <AnimatePresence>
        {isDragging && (
          <motion.div
            className="drop-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="drop-overlay-card">
              <FiUploadCloud size={48} />
              <span>Drop PDF to attach to this chat</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <PreviewModal
        isOpen={!!previewFile}
        onClose={() => setPreviewFile(null)}
        fileUrl={previewFile?.url}
        fileName={previewFile?.name}
      />
    </>
  );
}

export default App;

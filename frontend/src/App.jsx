import React, { useState, useEffect, useCallback } from "react";
import NavBar from "./pages/NavBar";
import AskQuestion from "./pages/AskQuestion";
import PreviewModal from "./components/PreviewModal";
import api, { API_BASE_URL } from "./api";
import { toast } from "react-toastify";

function App() {
  const [chatId, setChatId] = useState(() => {
    return localStorage.getItem("current_chat_id") || "";
  });
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);

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

import "../styles/navbar.css"; 
import { useState, useRef, useEffect } from "react";
import { AiOutlineClose } from "react-icons/ai";
import { FiFile } from "react-icons/fi";
import { AiOutlineUpload } from "react-icons/ai";
import { RiEdit2Fill } from "react-icons/ri";
import { motion, AnimatePresence } from "framer-motion";
import api from "../api";
import PreviewModal from "../components/PreviewModal";

function NavBar({ setUploadedFileName }) {
  const fileInputRef = useRef(null);
  const [fileName, setFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [showConfirmRemove, setShowConfirmRemove] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    const savedFileName = localStorage.getItem("uploadedFileName");
    if (savedFileName) {
      setFileName(savedFileName);
      setUploadedFileName(savedFileName);
    }
  }, [setUploadedFileName]);

  const handleButtonClick = () => {
    if (!loading) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      setLoading(true);
      const response = await api.post("/upload-pdf/", formData);
      localStorage.setItem("uploadedFileName", response.data.filename);
      setFileName(response.data.filename);
      setUploadedFileName(response.data.filename);
    } catch (error) {
      console.error("Error uploading file:", error);
      alert("Failed to upload file");
      fileInputRef.current.value = null;
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveFile = () => {
    setFileName("");
    setUploadedFileName("");
    fileInputRef.current.value = null;
    localStorage.removeItem("uploadedFileName");
    localStorage.removeItem(`chatHistory_${fileName}`);
    setShowConfirmRemove(false);
  };

  const togglePreview = () => {
    if (fileName) {
      setShowPreview(!showPreview);
    }
  };

  return (
    <div style={{ position: "fixed", top: 0, left: 0, width: "100%", zIndex: 1000 }}>
      <nav className="navbar navbar-light glass custom-navbar">
        <div className="container">
          <a className="navbar-brand d-flex align-items-center" href="#" style={{ fontWeight: 700, letterSpacing: "-0.5px" }}>
            <span className="brand-logo">PDF</span>
            <span className="brand-text ms-1">Reviewer</span>
          </a>
          
          <input
            type="file"
            accept="application/pdf"
            style={{ display: "none" }}
            ref={fileInputRef}
            onChange={handleFileChange}
          />
          
          <div className="ms-auto d-flex align-items-center">
            {loading ? (
              <div className="spinner-container me-3">
                <div className="spinner" />
              </div>
            ) : fileName ? (
              <div className="file-display d-flex align-items-center animate-fade-in">
                <div className="file-info me-2 d-flex align-items-center">
                  <FiFile className="me-1 text-primary d-none d-sm-inline" />
                  <span 
                    className="file-name-text preview-link" 
                    onClick={togglePreview}
                    title="Click to preview PDF"
                  >
                    {fileName}
                  </span>
                </div>
                
                <AnimatePresence mode="wait">
                  {showConfirmRemove ? (
                    <motion.div 
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.8, opacity: 0 }}
                      className="confirm-badge"
                    >
                      <span className="me-2 fw-semibold">Remove?</span>
                      <button onClick={handleRemoveFile} className="btn-yes">Yes</button>
                      <span className="divider">|</span>
                      <button onClick={() => setShowConfirmRemove(false)} className="btn-no">No</button>
                    </motion.div>
                  ) : (
                    <motion.div
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.8, opacity: 0 }}
                    >
                      <AiOutlineClose
                        onClick={() => setShowConfirmRemove(true)}
                        className="remove-icon"
                        title="Remove file"
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ) : null}

            <button 
              className={`upload-btn ${fileName ? 'btn-secondary' : 'btn-primary'}`} 
              onClick={handleButtonClick} 
              disabled={loading}
            >
              <span className="icon">
                {fileName ? <RiEdit2Fill /> : <AiOutlineUpload />}
              </span>
              <span className="text ms-2 d-none d-sm-inline">
                {loading ? "Working..." : fileName ? "Change PDF" : "Upload PDF"}
              </span>
            </button>
          </div>
        </div>
      </nav>

      <PreviewModal 
        isOpen={showPreview} 
        onClose={() => setShowPreview(false)} 
        fileUrl={`${import.meta.env.VITE_API_URL}/uploads/${fileName}`}
        fileName={fileName}
      />
    </div>
  );
}

export default NavBar; // Export the NavBar component

import "../styles/navbar.css";
import { useState, useRef } from "react";
import { AiOutlineClose, AiOutlineUpload } from "react-icons/ai";
import { FiFile, FiPlus } from "react-icons/fi";
import { motion, AnimatePresence } from "framer-motion";

function NavBar({ documents = [], loading = false, onUploadFile, onRemoveFile, onPreviewFile }) {
  const fileInputRef = useRef(null);
  const [confirmRemoveId, setConfirmRemoveId] = useState(null);

  const handleButtonClick = () => {
    if (!loading && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (file) {
      onUploadFile(file);
      event.target.value = "";
    }
  };

  return (
    <div style={{ position: "fixed", top: 0, left: 0, width: "100%", zIndex: 1000 }}>
      <nav className="navbar navbar-light glass custom-navbar">
        <div className="container">
          <a
            className="navbar-brand d-flex align-items-center"
            href="#"
            style={{ fontWeight: 700, letterSpacing: "-0.5px" }}
          >
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

          <div className="ms-auto d-flex align-items-center gap-2">
            {/* Attached Documents Chips */}
            {documents.length > 0 && (
              <div className="files-container me-2">
                {documents.map((doc) => {
                  const isConfirming = confirmRemoveId === doc.id;
                  const docTitle = doc.original_name || doc.filename;

                  return (
                    <div key={doc.id || doc.filename} className="file-display animate-fade-in">
                      <span
                        className={`file-status-dot ${doc.status}`}
                        title={doc.status === "ready" ? "Ready" : doc.status === "indexing" ? "Preparing..." : "Needs attention"}
                      />
                      <FiFile className="text-primary d-none d-sm-inline" />
                      <span
                        className="file-name-text preview-link"
                        onClick={() => onPreviewFile(doc)}
                        title={`Click to preview: ${docTitle}`}
                      >
                        {docTitle}
                      </span>

                      <AnimatePresence mode="wait">
                        {isConfirming ? (
                          <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.8, opacity: 0 }}
                            className="confirm-badge ms-1"
                          >
                            <span className="fw-semibold me-1">Del?</span>
                            <button
                              onClick={() => {
                                onRemoveFile(doc.id);
                                setConfirmRemoveId(null);
                              }}
                              className="btn-yes"
                            >
                              Yes
                            </button>
                            <span className="divider">|</span>
                            <button
                              onClick={() => setConfirmRemoveId(null)}
                              className="btn-no"
                            >
                              No
                            </button>
                          </motion.div>
                        ) : (
                          <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.8, opacity: 0 }}
                          >
                            <AiOutlineClose
                              onClick={() => setConfirmRemoveId(doc.id)}
                              className="remove-icon ms-1"
                              title="Remove file"
                            />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Upload Spinner or Button */}
            {loading ? (
              <div className="spinner-container me-2">
                <div className="spinner" />
              </div>
            ) : null}

            <button
              className={`upload-btn ${documents.length > 0 ? "btn-secondary" : "btn-primary"}`}
              onClick={handleButtonClick}
              disabled={loading}
              title={documents.length > 0 ? "Attach another PDF to this chat" : "Upload a PDF"}
            >
              <span className="icon">
                {documents.length > 0 ? <FiPlus /> : <AiOutlineUpload />}
              </span>
              <span className="text ms-2 d-none d-sm-inline">
                {loading ? "Working..." : documents.length > 0 ? "Add PDF" : "Upload PDF"}
              </span>
            </button>
          </div>
        </div>
      </nav>
    </div>
  );
}

export default NavBar;

import { motion, AnimatePresence } from "framer-motion";
import { AiOutlineClose } from "react-icons/ai";

function PreviewModal({ isOpen, onClose, fileUrl, fileName }) {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="modal-overlay" onClick={onClose}>
        <motion.div 
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="modal-content glass"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="modal-header">
            <h3>{fileName}</h3>
            <div className="modal-actions">
              <button className="close-modal" onClick={onClose} title="Close Preview">
                <AiOutlineClose />
              </button>
            </div>
          </div>
          <div className="modal-body">
            <iframe
              src={`${fileUrl}#toolbar=0`}
              title="PDF Preview"
              className="pdf-frame"
            />
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

export default PreviewModal;

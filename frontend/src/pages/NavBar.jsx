import "../styles/navbar.css"; 
import { useState, useRef, useEffect } from "react";
import { AiOutlineClose } from "react-icons/ai"; // Importing close icon
import { FiFile } from "react-icons/fi"; // Importing file icon
import { AiOutlineUpload } from "react-icons/ai"; // Importing upload icon
import { RiEdit2Fill } from "react-icons/ri"; // Importing edit icon
import api from "../api"; // Importing the API module for making HTTP requests

function NavBar({ setUploadedFileName }) {
  const fileInputRef = useRef(null); // Reference to the hidden file input element
  const [fileName, setFileName] = useState(""); // State to store the uploaded file's name
  const [loading, setLoading] = useState(false); // State to track the loading status

  // useEffect to load the previously uploaded file name from localStorage on component mount
  useEffect(() => {
    const savedFileName = localStorage.getItem("uploadedFileName");
    if (savedFileName) {
      setFileName(savedFileName); // Set the file name in state
      setUploadedFileName(savedFileName); // Update the parent component's state
    }
  }, []);

  // Function to handle the upload button click
  const handleButtonClick = () => {
    if (!loading) {
      fileInputRef.current.click(); // Trigger the hidden file input
    }
  };

  // Function to handle file selection
  const handleFileChange = async (event) => {
    const file = event.target.files[0]; // Get the selected file
    if (!file) return;

    const uploadedFileName = file.name; // Extract the file name
    setFileName(uploadedFileName); // Update the state with the file name
    setUploadedFileName(uploadedFileName); // Update the parent component's state

    const formData = new FormData(); // Create a FormData object to send the file
    formData.append("file", file);

    try {
      setLoading(true); // Set loading to true while the file is being uploaded
      const response = await api.post("/upload-pdf/", formData); // Make an API call to upload the file
      localStorage.setItem("uploadedFileName", response.data.filename); // Save the uploaded file name in localStorage
    } catch (error) {
      console.error("Error uploading file:", error); // Log the error
      alert("Failed to upload file"); // Show an error message to the user
    } finally {
      setLoading(false); // Reset the loading state
    }
  };

  // Function to handle file removal
  const handleRemoveFile = () => {
    setFileName(""); // Clear the file name state
    setUploadedFileName(""); // Clear the parent component's state
    fileInputRef.current.value = null; // Reset the file input field
    localStorage.removeItem("uploadedFileName"); // Remove the file name from localStorage
  };

  return (
    <div style={{ position: "fixed", width: "100%" }}>
      <nav className="navbar navbar-light bg-white custom-navbar">
        <div className="container">
          <a className="navbar-brand" href="#">
            PdfReviewer {/* Brand name */}
          </a>
          {/* Hidden file input for selecting a PDF */}
          <input
            type="file"
            accept="application/pdf"
            style={{ display: "none" }}
            ref={fileInputRef}
            onChange={handleFileChange}
          />
          <div className="ms-auto">
            {/* Show a spinner if loading, otherwise display the file name */}
            {loading ? (
              <div className="spinner" />
            ) : fileName ? (
              <div className="file-name">
                <FiFile /> {/* File icon */}
                {fileName} {/* Display the file name */}
              </div>
            ) : null}
          </div>
          {/* Show a close icon to remove the file if a file is uploaded */}
          {fileName && (
            <AiOutlineClose
              onClick={handleRemoveFile}
              style={{
                cursor: "pointer",
                color: "black",
                marginLeft: "10px",
                marginRight: "10px",
                height: "15px",
              }}
              title="Remove file"
            />
          )}
          {/* Upload/Change PDF button */}
          <button className="upload-pdf" onClick={handleButtonClick}>
            <span className="icon" style={{ marginLeft: "5px" }}>
              {fileName ? <RiEdit2Fill /> : <AiOutlineUpload />}{" "}
              {/* Show edit or upload icon */}
            </span>
            <span className="text">
              {fileName ? "Change PDF" : "Upload PDF"} {/* Button text */}
            </span>
          </button>
        </div>
      </nav>
    </div>
  );
}

export default NavBar; // Export the NavBar component

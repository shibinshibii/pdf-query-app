import NavBar from "./pages/NavBar"; 
import AskQuestion from "./pages/AskQuestion";
import { useState, useEffect} from "react"; 

function App() {
  // State to store the name of the uploaded file
  const [uploadedFileName, setUploadedFileName] = useState(() => {
    return localStorage.getItem("uploadedFileName") || "";
  });

  // Whenever uploadedFileName changes, store it in localStorage
  useEffect(() => {
    if (uploadedFileName) {
      localStorage.setItem("uploadedFileName", uploadedFileName);
    }
  }, [uploadedFileName]);
  return (
    <>
      {/* Render the NavBar component and pass the setUploadedFileName function as a prop */}
      <NavBar setUploadedFileName={setUploadedFileName} />

      {/* Render the AskQuestion component and pass the uploadedFileName state as a prop */}
      <AskQuestion uploadedFileName={uploadedFileName} />
    </>
  );
}

export default App; 

import { useEffect, useState } from "react";

function App() {
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch("http://localhost:8000/health");
        const data = await response.json();
        setData(data);
      } catch (error) {
        console.error("Error fetching data:", error);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="App">
      <h1>Problem Finder App</h1>
      <h2>Discover real-world problems worth building for.</h2>
      {data ? (
        <p>
          {data.status == "OK"
            ? `We are live with version ${data.version}!`
            : "Error fetching data"}
        </p>
      ) : (
        <p>Loading...</p>
      )}
    </div>
  );
}

export default App;

import { useState } from "react";
import "../../styles/home.css";
import heroImage from "../../assets/hero.png";

function QueryInput({ onAnalyze }) {

  const [topic, setTopic] = useState("");

  return (

    <section className="hero">

      <div className="hero-left">

        <h1>AI-Powered Research Claim Analysis</h1>

        <p>
          Analyze scientific claims across multiple research papers
          using intelligent multi-agent AI systems.
        </p>

        <div className="search-box">

          <input
            type="text"
            placeholder="Enter a research topic..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />

          <button onClick={() => onAnalyze(topic)}>
            Analyze
          </button>

        </div>

      </div>

      <div className="hero-right">

        <img
          src={heroImage}
          alt="Research AI"
        />

      </div>

    </section>

  );

}

export default QueryInput;
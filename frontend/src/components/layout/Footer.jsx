import { Link } from "react-router-dom";
import "../../styles/footer.css";

function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <h3>Research<span>ClaimAI</span></h3>
          <p>
            A multi-agent framework that finds, verifies and scores research
            claims across multiple papers.
          </p>
        </div>

        <nav className="footer-col" aria-label="Product">
          <h4>Product</h4>
          <Link to="/home">Home</Link>
          <Link to="/analysis">New analysis</Link>
          <Link to="/dashboard">Latest report</Link>
          <Link to="/account">My account</Link>
        </nav>

        <nav className="footer-col" aria-label="Project">
          <h4>Project</h4>
          <Link to="/about">About</Link>
          <span>Adithya Ajith</span>
          <span>Malavika Krishna</span>
          <span>Sheethal Krishna K K</span>
        </nav>

        <div className="footer-col">
          <h4>Guided by</h4>
          <span>Dr. Sindhu V</span>
          <span>Department of Computer Science</span>
          <span>CHRIST (Deemed to be University)</span>
        </div>
      </div>

      <div className="footer-bottom">
        <span>© 2026 ResearchClaimAI Team</span>
        <span>
          Results are a research aid. Always confirm against the original
          papers.
        </span>
      </div>
    </footer>
  );
}

export default Footer;

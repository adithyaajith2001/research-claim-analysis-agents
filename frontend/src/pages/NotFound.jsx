import { Link } from "react-router-dom";
import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";

function NotFound() {
  return (
    <>
      <Navbar />
      <main style={{ minHeight: "60vh", display: "grid", placeItems: "center", textAlign: "center", padding: "80px 24px", background: "#050816" }}>
        <div>
          <p style={{ color: "#60a5fa", fontWeight: 600, letterSpacing: "0.12em" }}>ERROR 404</p>
          <h1 style={{ fontSize: 40, margin: "10px 0" }}>This page doesn't exist</h1>
          <p style={{ color: "#9aa6bb", marginBottom: 26 }}>
            The link may be old or mistyped. Let's get you back on track.
          </p>
          <Link to="/home" style={{ display: "inline-block", padding: "13px 24px", borderRadius: 12, fontWeight: 600, background: "linear-gradient(135deg,#3b82f6,#8b5cf6)" }}>
            Back to home
          </Link>
        </div>
      </main>
      <Footer />
    </>
  );
}

export default NotFound;

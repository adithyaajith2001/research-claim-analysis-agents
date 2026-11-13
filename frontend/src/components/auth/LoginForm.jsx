import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { signInWithPopup } from "firebase/auth";
import { auth, googleProvider } from "../../firebase";
import { loginUser, setSession } from "../../services/authService";

import {
  FaBrain,
  FaEnvelope,
  FaLock,
  FaGoogle,
} from "react-icons/fa";

const LoginForm = () => {
  // ==========================================
  // STATE
  // ==========================================

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");

  const navigate = useNavigate();

  // ==========================================
  // NORMAL EMAIL/PASSWORD LOGIN
  // ==========================================

  const handleLogin = async (e) => {
    e.preventDefault();

    setError("");

    if (!email.trim() || !password.trim()) {
      setError("Please enter your email and password.");
      return;
    }

    try {
      await loginUser(email, password);
      navigate("/home");
    } catch (err) {
      setError(err.message || "Login failed. Please try again.");
    }
  };

  // ==========================================
  // GOOGLE LOGIN
  // ==========================================

  const handleGoogleLogin = async () => {
    try {
      setError("");

      console.log("Starting Google login...");

      const result = await signInWithPopup(
        auth,
        googleProvider
      );

      const user = result.user;

      console.log("Google login successful:", user);

      // Store Google user as the current session
      setSession({
        name: user.displayName || user.email,
        email: user.email,
        photoURL: user.photoURL,
        provider: "google",
      });

      // Navigate only after successful login
      navigate("/home");

    } catch (error) {
      console.error("FULL GOOGLE ERROR:", error);
      console.error("ERROR CODE:", error.code);
      console.error("ERROR MESSAGE:", error.message);

      if (error.code === "auth/popup-closed-by-user") {
        setError("Google login was cancelled.");

      } else if (error.code === "auth/popup-blocked") {
        setError(
          "Google login popup was blocked by the browser."
        );

      } else if (error.code === "auth/unauthorized-domain") {
        setError(
          "This website domain is not authorized in Firebase."
        );

      } else {
        setError(
          `Google login failed: ${error.code || "Unknown error"}`
        );
      }
    }
  };

  // ==========================================
  // UI
  // ==========================================

  return (
    <>
      {/* LOGO */}
      <div className="login-logo">
        <FaBrain />
      </div>

      {/* HEADING */}
      <h2>Welcome Back</h2>

      <p className="login-subtitle">
        Login to continue using
        <br />
        ResearchClaimAI
      </p>

      {/* ERROR MESSAGE */}
      <div className={`login-error ${error ? "show" : ""}`}>
        {error}
      </div>

      <form onSubmit={handleLogin}>

        {/* EMAIL */}
        <div className="input-group">
          <FaEnvelope className="input-icon" />

          <input
            type="email"
            placeholder="Email Address"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setError("");
            }}
            required
          />
        </div>

        {/* PASSWORD */}
        <div className="input-group">
          <FaLock className="input-icon" />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setError("");
            }}
            required
          />
        </div>

        {/* LOGIN OPTIONS */}
        <div className="login-options">

          <label>
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) =>
                setRememberMe(e.target.checked)
              }
            />

            Remember Me
          </label>

          <span
            className="forgot-password"
            onClick={() =>
              alert(
                "Password recovery will be available soon."
              )
            }
          >
            Forgot Password?
          </span>

        </div>

        {/* LOGIN BUTTON */}
        <button
          className="login-btn"
          type="submit"
        >
          Login
        </button>

        {/* OR */}
        <div className="divider">
          OR
        </div>

        {/* GOOGLE LOGIN */}
        <button
          type="button"
          className="google-btn"
          onClick={handleGoogleLogin}
        >
          <FaGoogle />
          Continue with Google
        </button>

      </form>

      {/* SIGN UP */}
      <div className="signup-text">
        Don't have an account?

        <span
          onClick={() => navigate("/signup")}
        >
          {" "}Sign Up
        </span>
      </div>
    </>
  );
};

export default LoginForm;
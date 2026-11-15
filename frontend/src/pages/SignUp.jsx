import React, { useState } from "react";
import { registerUser } from "../services/authService";
import { useLocation, useNavigate } from "react-router-dom";

import {
  FaBrain,
  FaUser,
  FaEnvelope,
  FaLock,
} from "react-icons/fa";

function SignUp() {
  const navigate = useNavigate();
  const location = useLocation();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [success, setSuccess] = useState(false);

  const [error, setError] = useState("");

  const handleSignUp = async (e) => {
    e.preventDefault();
    setError("");

    if (!name.trim() || !email.trim() || !password) {
      setError("Please fill in all the fields.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      await registerUser({ name, email, password });
    } catch (err) {
      setError(err.message || "Could not create the account.");
      return;
    }

    setSuccess(true);

    // Redirect to Login page after 1.8 seconds
    setTimeout(() => {
      navigate("/login", { state: location.state });
    }, 1800);
  };

  return (
    <div className="signup-page">

      <div className="signup-card">

        {/* Logo */}
        <div className="signup-logo">
          <FaBrain />
        </div>

        {/* Heading */}
        <h1>Create Account</h1>

        <p className="signup-subtitle">
          Create your ResearchClaimAI account
        </p>

        {/* SUCCESS MESSAGE */}
        {success && (
          <div className="signup-success">
            <strong>✓ Account created successfully!</strong>

            <span>
              You can now log in to ResearchClaimAI.
            </span>

            <small>
              Redirecting to Login...
            </small>
          </div>
        )}

        {/* SIGNUP FORM */}
        {!success && (
          <form onSubmit={handleSignUp}>

            <div className={`login-error ${error ? "show" : ""}`} role="alert">
              {error}
            </div>

            {/* Full Name */}
            <div className="input-group">

              <FaUser className="input-icon" />

              <input
                type="text"
                placeholder="Full Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />

            </div>

            {/* Email */}
            <div className="input-group">

              <FaEnvelope className="input-icon" />

              <input
                type="email"
                placeholder="Email Address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />

            </div>

            {/* Password */}
            <div className="input-group">

              <FaLock className="input-icon" />

              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />

            </div>

            {/* Confirm Password */}
            <div className="input-group">

              <FaLock className="input-icon" />

              <input
                type="password"
                placeholder="Confirm Password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />

            </div>

            {/* Create Account Button */}
            <button
              type="submit"
              className="signup-btn"
            >
              Create Account
            </button>

          </form>
        )}

        {/* Login Link */}
        <div className="login-text">

          Already have an account?

          <span onClick={() => navigate("/login", { state: location.state })}>
            {" "}Login
          </span>

        </div>

      </div>

    </div>
  );
}

export default SignUp;
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  FaBrain,
  FaUser,
  FaEnvelope,
  FaLock,
} from "react-icons/fa";

function SignUp() {
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [success, setSuccess] = useState(false);

  const handleSignUp = (e) => {
    e.preventDefault();

    // Check whether passwords match
    if (password !== confirmPassword) {
      alert("Passwords do not match.");
      return;
    }
// Save user information in localStorage
const userData = {
  name,
  email,
  password,
};

localStorage.setItem(
  "researchClaimUser",
  JSON.stringify(userData)
);

setSuccess(true);


    // Redirect to Login page after 1.8 seconds
    setTimeout(() => {
      navigate("/");
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

          <span onClick={() => navigate("/")}>
            {" "}Login
          </span>

        </div>

      </div>

    </div>
  );
}

export default SignUp;
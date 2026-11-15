import React from "react";
import { Link } from "react-router-dom";
import "../../styles/loginNew.css";

import LeftPanel from "./LeftPanel";
import RightPanel from "./RightPanel";

function LoginPage() {
  return (
    <div className="login-page">
      <Link to="/" className="login-back">← Back to home</Link>
      <LeftPanel />
      <RightPanel />
    </div>
  );
}

export default LoginPage;

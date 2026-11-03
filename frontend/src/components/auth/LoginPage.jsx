import React from "react";
import "../../styles/loginNew.css";  // <-- ADD THIS

import LeftPanel from "./LeftPanel";
import RightPanel from "./RightPanel";

function LoginPage() {
  return (
    <div className="login-page">
      <LeftPanel />
      <RightPanel />
    </div>
  );
}

export default LoginPage;
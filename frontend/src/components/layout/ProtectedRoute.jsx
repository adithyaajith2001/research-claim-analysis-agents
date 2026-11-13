import { Navigate } from "react-router-dom";

import { getSession } from "../../services/authService";

// Only signed-in people can open the app pages.
function ProtectedRoute({ children }) {
  if (!getSession()) {
    return <Navigate to="/" replace />;
  }

  return children;
}

export default ProtectedRoute;

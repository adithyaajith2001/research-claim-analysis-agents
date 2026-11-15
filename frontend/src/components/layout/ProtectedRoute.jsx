import { Navigate, useLocation } from "react-router-dom";

import { getSession } from "../../services/authService";

// Only signed-in people can open the app pages. Everyone else is sent to the
// login page and brought back here afterwards.
function ProtectedRoute({ children }) {
  const location = useLocation();

  if (!getSession()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}

export default ProtectedRoute;

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Loading from "./components/loading/Loading";

import Login from "./pages/Login";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import SignUp from "./pages/SignUp";
import Analysis from "./pages/Analysis";
import About from "./pages/About";
import Account from "./pages/Account";
import Explore from "./pages/Explore";
import ProtectedRoute from "./components/layout/ProtectedRoute";
import NotFound from "./pages/NotFound";
import { getSession } from "./services/authService";


function App() {

  return (

    <BrowserRouter>

      <Routes>

        {/* =====================================================
            LOGIN
        ===================================================== */}

        <Route
          path="/"
          element={<Home />}
        />

        <Route
          path="/login"
          element={getSession() ? <Navigate to="/home" replace /> : <Login />}
        />

        <Route path="/explore" element={<Explore />} />


        {/* =====================================================
            HOME
        ===================================================== */}

        <Route
          path="/home"
          element={<Home />}
        />


        {/* =====================================================
            ABOUT
        ===================================================== */}

        <Route
          path="/about"
          element={<About />}
        />


        {/* =====================================================
            ANALYSIS
        ===================================================== */}

        <Route
          path="/analysis"
          element={<ProtectedRoute><Analysis /></ProtectedRoute>}
        />


        {/* =====================================================
            LOADING
        ===================================================== */}

        <Route
          path="/loading"
          element={<ProtectedRoute><Loading /></ProtectedRoute>}
        />


        {/* =====================================================
            DASHBOARD
        ===================================================== */}

        <Route
          path="/dashboard"
          element={<ProtectedRoute><Dashboard /></ProtectedRoute>}
        />


        <Route
          path="/account"
          element={<ProtectedRoute><Account /></ProtectedRoute>}
        />


        {/* =====================================================
            SIGN UP
        ===================================================== */}

        <Route
          path="/signup"
          element={<SignUp />}
        />

        <Route path="*" element={<NotFound />} />

      </Routes>

    </BrowserRouter>

  );

}


export default App;
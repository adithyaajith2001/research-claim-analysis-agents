import { BrowserRouter, Routes, Route } from "react-router-dom";

import Loading from "./components/loading/Loading";

import Login from "./pages/Login";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import SignUp from "./pages/SignUp";
import Analysis from "./pages/Analysis";
import About from "./pages/About";
import Account from "./pages/Account";
import ProtectedRoute from "./components/layout/ProtectedRoute";


function App() {

  return (

    <BrowserRouter>

      <Routes>

        {/* =====================================================
            LOGIN
        ===================================================== */}

        <Route
          path="/"
          element={<Login />}
        />


        {/* =====================================================
            HOME
        ===================================================== */}

        <Route
          path="/home"
          element={<ProtectedRoute><Home /></ProtectedRoute>}
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

      </Routes>

    </BrowserRouter>

  );

}


export default App;
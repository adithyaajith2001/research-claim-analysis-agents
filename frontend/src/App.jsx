import { BrowserRouter, Routes, Route } from "react-router-dom";

import Loading from "./components/loading/Loading";

import Login from "./pages/Login";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import SignUp from "./pages/SignUp";
import Analysis from "./pages/Analysis";
import About from "./pages/About";


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
          element={<Analysis />}
        />


        {/* =====================================================
            LOADING
        ===================================================== */}

        <Route
          path="/loading"
          element={<Loading />}
        />


        {/* =====================================================
            DASHBOARD
        ===================================================== */}

        <Route
          path="/dashboard"
          element={<Dashboard />}
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
import { Link, useLocation } from "react-router-dom";
import { FaBell, FaUserCircle } from "react-icons/fa";

import "../../styles/navbar.css";


function Navbar() {

  const location = useLocation();


  return (

    <nav className="navbar">


      {/* =====================================================
          LOGO
      ===================================================== */}

      <div className="logo">

        🔬 <span>ResearchClaimAI</span>

      </div>


      {/* =====================================================
          NAVIGATION LINKS
      ===================================================== */}

      <ul className="nav-links">


        {/* HOME */}

        <li>

          <Link
            to="/"
            className={
              location.pathname === "/"
                ? "active"
                : ""
            }
          >

            Home

          </Link>

        </li>


        {/* DASHBOARD */}

        <li>

          <Link
            to="/dashboard"
            className={
              location.pathname === "/dashboard"
                ? "active"
                : ""
            }
          >

            Dashboard

          </Link>

        </li>


        {/* ANALYSIS */}

        <li>

          <Link
            to="/analysis"
            className={
              location.pathname === "/analysis"
                ? "active"
                : ""
            }
          >

            Analysis

          </Link>

        </li>


        {/* ABOUT */}

        <li>

          <Link
            to="/about"
            className={
              location.pathname === "/about"
                ? "active"
                : ""
            }
          >

            About

          </Link>

        </li>


      </ul>


      {/* =====================================================
          RIGHT SIDE
      ===================================================== */}

      <div className="nav-right">


        <FaBell className="nav-icon" />


        <div className="user-box">

          <FaUserCircle />

          <span>
            Admin
          </span>

        </div>


      </div>


    </nav>

  );

}


export default Navbar;
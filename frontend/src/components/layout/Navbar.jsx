import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { FaBell, FaUserCircle } from "react-icons/fa";
import { signOut } from "firebase/auth";

import { auth } from "../../firebase";
import { clearSession, getSession } from "../../services/authService";
import {
  getNotifications,
  markNotificationsSeen,
  timeAgo
} from "../../services/historyService";

import "../../styles/navbar.css";


function Navbar() {

  const location = useLocation();
  const navigate = useNavigate();

  const user = getSession();

  const [openMenu, setOpenMenu] = useState(null);
  const [notifications, setNotifications] = useState(() =>
    user ? getNotifications(user.email) : []
  );

  const rightRef = useRef(null);

  const unreadCount = notifications.filter((item) => item.unread).length;
  const displayName = user?.name || user?.email || "Guest";
  const initial = displayName.trim().charAt(0).toUpperCase();


  // Close menus when clicking elsewhere or pressing Escape
  useEffect(() => {
    const onClick = (event) => {
      if (rightRef.current && !rightRef.current.contains(event.target)) {
        setOpenMenu(null);
      }
    };
    const onKey = (event) => {
      if (event.key === "Escape") setOpenMenu(null);
    };

    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);

    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const toggleBell = () => {
    if (openMenu === "bell") {
      setOpenMenu(null);
      return;
    }

    setOpenMenu("bell");

    if (user) {
      markNotificationsSeen(user.email);
      // Keep the unread dots visible while the panel is open
    }
  };

  const toggleUser = () => {
    setOpenMenu(openMenu === "user" ? null : "user");
  };

  const refreshNotifications = () => {
    if (user) setNotifications(getNotifications(user.email));
  };

  const logout = async () => {
    try {
      await signOut(auth);
    } catch {
      /* not signed in with Google: ignore */
    }

    clearSession();
    navigate("/", { replace: true });
  };

  const goTo = (path) => {
    setOpenMenu(null);
    navigate(path);
  };


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

      <div className="nav-right" ref={rightRef}>


        {/* NOTIFICATIONS */}

        <div className="nav-menu-wrap">

          <button
            type="button"
            className="nav-bell"
            aria-label="Notifications"
            aria-expanded={openMenu === "bell"}
            onClick={() => {
              refreshNotifications();
              toggleBell();
            }}
          >
            <FaBell className="nav-icon" />
            {unreadCount > 0 && openMenu !== "bell" && (
              <span className="nav-badge">{unreadCount}</span>
            )}
          </button>

          {openMenu === "bell" && (
            <div className="nav-dropdown nav-notifications" role="menu">
              <div className="nav-dropdown-head">Notifications</div>

              {notifications.length === 0 ? (
                <p className="nav-empty">
                  Nothing yet. Finished analyses will show up here.
                </p>
              ) : (
                notifications.map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    className={
                      item.unread ? "nav-note nav-note-unread" : "nav-note"
                    }
                    onClick={() => goTo("/account")}
                  >
                    <strong>{item.title}</strong>
                    <span>{item.text}</span>
                    <small>{timeAgo(item.timestamp)}</small>
                  </button>
                ))
              )}

              <button
                type="button"
                className="nav-dropdown-link"
                onClick={() => goTo("/account")}
              >
                View all history
              </button>
            </div>
          )}

        </div>


        {/* ACCOUNT */}

        <div className="nav-menu-wrap">

          <button
            type="button"
            className="user-box"
            aria-expanded={openMenu === "user"}
            onClick={toggleUser}
          >
            {user?.photoURL ? (
              <img
                className="nav-avatar"
                src={user.photoURL}
                alt=""
                referrerPolicy="no-referrer"
              />
            ) : user ? (
              <span className="nav-avatar nav-avatar-initial">{initial}</span>
            ) : (
              <FaUserCircle />
            )}

            <span className="nav-username">{displayName}</span>
          </button>

          {openMenu === "user" && (
            <div className="nav-dropdown nav-account" role="menu">
              {user ? (
                <>
                  <div className="nav-account-head">
                    <strong>{displayName}</strong>
                    <span>{user.email}</span>
                  </div>

                  <button
                    type="button"
                    className="nav-dropdown-link"
                    onClick={() => goTo("/account")}
                  >
                    My account
                  </button>

                  <button
                    type="button"
                    className="nav-dropdown-link"
                    onClick={() => goTo("/account#history")}
                  >
                    Search history
                  </button>

                  <button
                    type="button"
                    className="nav-dropdown-link nav-logout"
                    onClick={logout}
                  >
                    Log out
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="nav-dropdown-link"
                  onClick={() => goTo("/")}
                >
                  Log in
                </button>
              )}
            </div>
          )}

        </div>


      </div>


    </nav>

  );

}


export default Navbar;
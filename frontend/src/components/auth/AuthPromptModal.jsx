import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { FaTimes, FaLock } from "react-icons/fa";

import "../../styles/authPrompt.css";

// "Sign in to continue" popup shown when a visitor tries to analyse a question.
function AuthPromptModal({ topic, onClose }) {
  const navigate = useNavigate();
  const firstButton = useRef(null);
  const dialog = useRef(null);

  useEffect(() => {
    const previous = document.activeElement;
    firstButton.current?.focus();

    const onKey = (event) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }

      // Keep Tab inside the popup.
      if (event.key === "Tab" && dialog.current) {
        const items = dialog.current.querySelectorAll("button, a[href]");
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", onKey);
    const scrollY = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = scrollY;
      previous?.focus?.();
    };
  }, [onClose]);

  const go = (path) => {
    onClose();
    navigate(path, { state: { from: "/analysis", topic } });
  };

  return (
    <div
      className="ap-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="ap-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ap-title"
        ref={dialog}
      >
        <button type="button" className="ap-close" aria-label="Close" onClick={onClose}>
          <FaTimes />
        </button>

        <span className="ap-icon" aria-hidden="true"><FaLock /></span>

        <h2 id="ap-title">Sign in to run your analysis</h2>
        <p className="ap-text">
          It's free. Your searches and reports are saved to your account so
          you can reopen them any time.
        </p>

        {topic && (
          <div className="ap-topic">
            <small>Your question</small>
            <strong>{topic}</strong>
          </div>
        )}

        <button type="button" className="ap-primary" ref={firstButton} onClick={() => go("/login")}>
          Sign in
        </button>
        <button type="button" className="ap-secondary" onClick={() => go("/signup")}>
          Create a free account
        </button>

        <p className="ap-fine">We'll bring your question with you.</p>
      </div>
    </div>
  );
}

export default AuthPromptModal;

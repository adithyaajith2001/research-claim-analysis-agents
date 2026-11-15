import { createContext, useCallback, useContext, useMemo, useState } from "react";

import AuthPromptModal from "../components/auth/AuthPromptModal";

const AuthPromptContext = createContext({ openAuthPrompt: () => {} });

// Lets any page ask a visitor to sign in without leaving the page they are on.
export function AuthPromptProvider({ children }) {
  const [topic, setTopic] = useState(null);

  const openAuthPrompt = useCallback((question = "") => setTopic(String(question)), []);
  const close = useCallback(() => setTopic(null), []);

  const value = useMemo(() => ({ openAuthPrompt }), [openAuthPrompt]);

  return (
    <AuthPromptContext.Provider value={value}>
      {children}
      {topic !== null && <AuthPromptModal topic={topic} onClose={close} />}
    </AuthPromptContext.Provider>
  );
}

export const useAuthPrompt = () => useContext(AuthPromptContext);

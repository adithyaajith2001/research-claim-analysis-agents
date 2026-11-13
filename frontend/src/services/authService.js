// Local account handling for ResearchClaimAI.
//
// Accounts are kept in this browser (localStorage). Passwords are never
// stored as plain text: each is salted and hashed with SHA-256 first.
// Google sign-in goes through Firebase and is stored as a session only.
//
// This is suitable for a demo. For production, replace it with Firebase
// email/password sign-in (needs to be switched on in the Firebase console).

const USERS_KEY = "researchClaimUsers";
const LEGACY_USER_KEY = "researchClaimUser";
const SESSION_KEY = "loggedInUser";

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: ignore */
  }
}

function normaliseEmail(email) {
  return String(email || "").trim().toLowerCase();
}

async function hashPassword(password, salt) {
  const data = new TextEncoder().encode(`${salt}:${password}`);
  const digest = await crypto.subtle.digest("SHA-256", data);

  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function newSalt() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function allUsers() {
  const users = read(USERS_KEY, {});

  // Move an account made by the old sign-up page (single user, plain
  // password) into the new store. It is hashed on first successful login.
  const legacy = read(LEGACY_USER_KEY, null);

  if (legacy?.email && !users[normaliseEmail(legacy.email)]) {
    users[normaliseEmail(legacy.email)] = {
      name: legacy.name || legacy.email,
      email: normaliseEmail(legacy.email),
      legacyPassword: legacy.password,
      createdAt: new Date().toISOString()
    };
    write(USERS_KEY, users);
  }

  return users;
}

export async function registerUser({ name, email, password }) {
  const key = normaliseEmail(email);
  const users = allUsers();

  if (users[key]) {
    throw new Error("An account with this email already exists. Please log in.");
  }

  const salt = newSalt();

  users[key] = {
    name: String(name || "").trim() || key,
    email: key,
    salt,
    passwordHash: await hashPassword(password, salt),
    createdAt: new Date().toISOString()
  };

  write(USERS_KEY, users);
  localStorage.removeItem(LEGACY_USER_KEY);
}

export async function loginUser(email, password) {
  const key = normaliseEmail(email);
  const users = allUsers();
  const account = users[key];

  if (!account) {
    throw new Error("No account found for this email. Please sign up first.");
  }

  let ok = false;

  if (account.passwordHash) {
    ok = (await hashPassword(password, account.salt)) === account.passwordHash;
  } else if (account.legacyPassword !== undefined) {
    ok = account.legacyPassword === password;

    if (ok) {
      // Upgrade the old plain-text password to a salted hash.
      const salt = newSalt();
      account.salt = salt;
      account.passwordHash = await hashPassword(password, salt);
      delete account.legacyPassword;
      users[key] = account;
      write(USERS_KEY, users);
    }
  }

  if (!ok) {
    throw new Error("Invalid email or password. Please try again.");
  }

  const session = {
    name: account.name,
    email: account.email,
    provider: "password",
    createdAt: account.createdAt
  };

  setSession(session);
  return session;
}

export function setSession(user) {
  write(SESSION_KEY, {
    ...user,
    email: normaliseEmail(user.email)
  });
}

export function getSession() {
  const user = read(SESSION_KEY, null);
  return user?.email ? user : null;
}

export function clearSession() {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}

export function updateDisplayName(newName) {
  const session = getSession();
  const name = String(newName || "").trim();

  if (!session || !name) return session;

  const users = allUsers();

  if (users[session.email]) {
    users[session.email].name = name;
    write(USERS_KEY, users);
  }

  const updated = { ...session, name };
  setSession(updated);
  return updated;
}

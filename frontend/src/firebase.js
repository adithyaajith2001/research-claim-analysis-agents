import { initializeApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider
} from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyCy3_PgDX-r3o4eOyuVwd9hO1icgj1-Xuc",
  authDomain: "researchclaimai.firebaseapp.com",
  projectId: "researchclaimai",
  storageBucket: "researchclaimai.firebasestorage.app",
  messagingSenderId: "855074620084",
  appId: "1:855074620084:web:54abd1289d88f5b526cde1"
};

const app = initializeApp(firebaseConfig);

const auth = getAuth(app);

const googleProvider = new GoogleAuthProvider();

export { app, auth, googleProvider };
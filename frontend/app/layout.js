import "./globals.css";

export const metadata = {
  title: "ResearchClaimAI",
  description:
    "Multi-agent framework for autonomous analysis and verification of research claims across multiple papers.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

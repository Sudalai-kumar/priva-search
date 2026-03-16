import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Priva-Search — Know who's selling your data",
  description:
    "Search any brand and instantly get a Privacy Scorecard — a clear breakdown of how that company handles your personal data, powered by AI analysis of their official privacy policy.",
  keywords: ["privacy", "data", "GDPR", "CCPA", "privacy policy", "scorecard"],
  openGraph: {
    title: "Priva-Search",
    description: "Know who's selling your data before you sign up.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-[#09090b] text-zinc-100 antialiased min-h-screen">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

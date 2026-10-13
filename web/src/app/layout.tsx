import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";

import { Nav } from "@/components/Nav";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Adaptive RAG",
  description: "Upload documents, see how each is indexed, and ask questions with explained answers.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full font-sans">
        {/* The nav reads the URL, so Next.js needs a Suspense boundary around it */}
        <Suspense fallback={null}>
          <Nav />
        </Suspense>
        <main className="app-main">
          <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-8 sm:py-10">{children}</div>
        </main>
      </body>
    </html>
  );
}

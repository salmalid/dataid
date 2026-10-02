import type { Metadata, Viewport } from "next";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";


export const metadata: Metadata = {
  title: {
    default: "dataid — The AI Operating System for Data Scientists",
    template: "%s · dataid",
  },
  description:
    "Upload a dataset, describe your goal, and watch a team of AI agents profile, clean, engineer, train, explain, deploy and monitor a complete ML pipeline.",
  keywords: [
    "AutoML",
    "machine learning",
    "data science",
    "multi-agent",
    "SHAP",
    "MLOps",
    "model monitoring",
  ],
  openGraph: {
    title: "dataid — The AI Operating System for Data Scientists",
    description: "From raw data to production in minutes.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fafafa" },
    { media: "(prefers-color-scheme: dark)", color: "#050506" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}

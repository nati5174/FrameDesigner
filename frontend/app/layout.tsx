import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const ibmPlexSans = IBM_Plex_Sans({
  variable: "--font-ibm-plex-sans",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600"],
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-plex-mono",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://frame-designer-five.vercel.app"),
  title: "Frame Designer",
  description: "Describe a frame, get a 3D model, cut list, cost and load estimate — aluminium T-slot extrusion.",
  openGraph: {
    title: "Frame Designer",
    description: "Describe a frame, get a 3D model, cut list, cost and load estimate — aluminium T-slot extrusion.",
    url: "https://frame-designer-five.vercel.app",
    siteName: "Frame Designer",
    images: [{ url: "/pass.png", width: 1600, height: 900, alt: "A passing frame design" }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Frame Designer",
    description: "Describe a frame, get a 3D model, cut list, cost and load estimate — aluminium T-slot extrusion.",
    images: ["/pass.png"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${ibmPlexSans.variable} ${ibmPlexMono.variable} h-full antialiased`}
    >
      <body className="h-full">{children}</body>
    </html>
  );
}

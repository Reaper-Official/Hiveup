import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { Providers } from './providers'
import './globals.css'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
})

export const metadata: Metadata = {
  title: 'Contest Platform - Créez des concours viraux',
  description: 'Plateforme SaaS de création et gestion de concours avec intégrations sociales.',
  keywords: 'concours, giveaway, contest, sweepstake, social media',
  authors: [{ name: 'Contest Platform' }],
  openGraph: {
    title: 'Contest Platform',
    description: 'Créez des concours viraux en quelques minutes',
    url: 'https://contest-platform.com',
    siteName: 'Contest Platform',
    locale: 'fr_FR',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Contest Platform',
    description: 'Créez des concours viraux en quelques minutes',
  },
  robots: {
    index: true,
    follow: true,
  },
  manifest: '/manifest.json',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: 'white' },
    { media: '(prefers-color-scheme: dark)', color: 'black' },
  ],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={inter.variable}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
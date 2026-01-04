import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AI Calendar Assistant',
  description: 'AI-powered Telegram bot for calendar and notes management',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-gray-50">{children}</body>
    </html>
  )
}

'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

interface User {
  id: number
  first_name: string
  last_name?: string
  username?: string
  photo_url?: string
}

export default function Dashboard() {
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check if user is authenticated
    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/')
      return
    }

    // Try to get user info from localStorage or decode token
    try {
      // For now, just show that user is logged in
      // In production, you'd validate token with API
      setUser({
        id: 0,
        first_name: 'User'
      })
    } catch {
      router.push('/')
    } finally {
      setLoading(false)
    }
  }, [router])

  const handleLogout = () => {
    localStorage.removeItem('token')
    router.push('/')
  }

  if (loading) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center p-8">
        <div className="text-gray-500">Loading...</div>
      </main>
    )
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-2xl w-full bg-white rounded-2xl shadow-lg p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            AI Calendar Assistant
          </h1>
          <p className="text-green-600">
            Logged in as {user?.first_name}
          </p>
        </div>

        <div className="space-y-6">
          <div className="bg-blue-50 rounded-lg p-6">
            <h2 className="font-semibold text-blue-900 mb-4">Connected Integrations</h2>
            <div className="space-y-3">
              <IntegrationCard
                name="Google Calendar"
                status="not_connected"
                href="/integrations/google"
              />
              <IntegrationCard
                name="Microsoft Outlook"
                status="not_connected"
                href="/integrations/microsoft"
              />
              <IntegrationCard
                name="Notion"
                status="not_connected"
                href="/integrations/notion"
              />
            </div>
          </div>

          <div className="bg-gray-50 rounded-lg p-6">
            <h2 className="font-semibold text-gray-900 mb-4">How to use</h2>
            <ol className="text-sm text-gray-700 space-y-2 list-decimal list-inside">
              <li>Connect your calendar above</li>
              <li>Send a voice or text message to @corbentask_bot</li>
              <li>The bot will create events in your calendar</li>
            </ol>
          </div>

          <div className="text-center">
            <a
              href="https://t.me/corbentask_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block bg-blue-500 text-white px-6 py-3 rounded-lg hover:bg-blue-600 transition"
            >
              Open Bot in Telegram
            </a>
          </div>

          <div className="text-center pt-4 border-t">
            <button
              onClick={handleLogout}
              className="text-gray-500 hover:text-gray-700 text-sm"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </main>
  )
}

function IntegrationCard({
  name,
  status,
  href
}: {
  name: string
  status: 'connected' | 'not_connected'
  href: string
}) {
  return (
    <div className="flex items-center justify-between bg-white p-4 rounded-lg border">
      <span className="font-medium text-gray-800">{name}</span>
      {status === 'connected' ? (
        <span className="text-green-600 text-sm">Connected</span>
      ) : (
        <a
          href={href}
          className="text-blue-500 hover:text-blue-600 text-sm"
        >
          Connect
        </a>
      )}
    </div>
  )
}

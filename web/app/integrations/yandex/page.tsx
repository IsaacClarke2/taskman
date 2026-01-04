'use client'

import { Suspense, useState } from 'react'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://corben.pro'

function YandexIntegrationContent() {
  const router = useRouter()
  const [status, setStatus] = useState<'form' | 'connecting' | 'success' | 'error'>('form')
  const [error, setError] = useState<string | null>(null)
  const [username, setUsername] = useState('')
  const [appPassword, setAppPassword] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus('connecting')
    setError(null)

    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/')
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/integrations/yandex/connect`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: username,
          app_password: appPassword,
        }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to connect Yandex Calendar')
      }

      setStatus('success')

      setTimeout(() => {
        router.push('/dashboard')
      }, 2000)
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Failed to connect')
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-lg p-8 text-center">
        <div className="mb-6">
          <svg className="w-16 h-16 mx-auto" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="12" fill="#FC3F1D"/>
            <path fill="#fff" d="M13.5 6h-1.8v5.5L9 6H7l4 7.5V18h1.5v-4.5L16.5 6h-2l-1 5.5z"/>
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          Yandex Calendar
        </h1>

        {status === 'form' && (
          <form onSubmit={handleSubmit} className="space-y-4 text-left">
            <p className="text-gray-600 text-sm mb-4 text-center">
              Connect using your Yandex app-specific password.
              <br/>
              <a
                href="https://id.yandex.ru/security/app-passwords"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:underline"
              >
                Create app password
              </a>
            </p>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Yandex Login
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="your.email@yandex.ru"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                App Password
              </label>
              <input
                type="password"
                value={appPassword}
                onChange={(e) => setAppPassword(e.target.value)}
                placeholder="App-specific password"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                required
              />
              <p className="text-xs text-gray-500 mt-1">
                Not your main password! Use an app-specific password.
              </p>
            </div>

            <button
              type="submit"
              className="w-full bg-red-500 text-white px-6 py-3 rounded-lg hover:bg-red-600 transition font-medium"
            >
              Connect Yandex Calendar
            </button>

            <button
              type="button"
              onClick={() => router.push('/dashboard')}
              className="w-full text-gray-500 hover:text-gray-700 text-sm py-2"
            >
              Cancel
            </button>
          </form>
        )}

        {status === 'connecting' && (
          <div>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500 mx-auto mb-4"></div>
            <p className="text-gray-600">Connecting to Yandex Calendar...</p>
          </div>
        )}

        {status === 'success' && (
          <div>
            <div className="text-green-500 text-5xl mb-4">&#10003;</div>
            <p className="text-green-600 font-medium">Successfully connected!</p>
            <p className="text-gray-500 text-sm mt-2">Redirecting to dashboard...</p>
          </div>
        )}

        {status === 'error' && (
          <div>
            <div className="text-red-500 text-5xl mb-4">&#10005;</div>
            <p className="text-red-600 font-medium mb-4">{error}</p>
            <button
              onClick={() => {
                setStatus('form')
                setError(null)
              }}
              className="bg-red-500 text-white px-6 py-2 rounded-lg hover:bg-red-600 transition"
            >
              Try Again
            </button>
            <button
              onClick={() => router.push('/dashboard')}
              className="block mx-auto mt-4 text-gray-500 hover:text-gray-700 text-sm"
            >
              Back to Dashboard
            </button>
          </div>
        )}
      </div>
    </main>
  )
}

function LoadingFallback() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-lg p-8 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500 mx-auto mb-4"></div>
        <p className="text-gray-600">Loading...</p>
      </div>
    </main>
  )
}

export default function YandexIntegration() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <YandexIntegrationContent />
    </Suspense>
  )
}

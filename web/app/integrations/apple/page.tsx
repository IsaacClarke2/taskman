'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://corben.pro'

export default function AppleIntegration() {
  const router = useRouter()
  const [status, setStatus] = useState<'form' | 'connecting' | 'success' | 'error'>('form')
  const [error, setError] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [appPassword, setAppPassword] = useState('')

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus('connecting')
    setError(null)

    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/')
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/integrations/apple-calendar`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          app_password: appPassword,
        }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to connect Apple Calendar')
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
      <div className="max-w-md w-full bg-white rounded-2xl shadow-lg p-8">
        <div className="text-center mb-6">
          <svg className="w-16 h-16 mx-auto" viewBox="0 0 24 24">
            <path fill="#000" d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-2 text-center">
          Apple Calendar
        </h1>

        {status === 'form' && (
          <>
            <p className="text-gray-600 text-sm mb-6 text-center">
              Connect via iCloud CalDAV using an app-specific password
            </p>

            <form onSubmit={handleConnect} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                  Apple ID (Email)
                </label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@icloud.com"
                  required
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                  App-Specific Password
                </label>
                <input
                  type="password"
                  id="password"
                  value={appPassword}
                  onChange={(e) => setAppPassword(e.target.value)}
                  placeholder="xxxx-xxxx-xxxx-xxxx"
                  required
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <button
                type="submit"
                className="w-full bg-gray-900 text-white py-3 rounded-lg hover:bg-gray-800 transition font-medium"
              >
                Connect Calendar
              </button>
            </form>

            <div className="mt-6 p-4 bg-blue-50 rounded-lg">
              <h3 className="font-medium text-blue-900 mb-2">How to get an app-specific password:</h3>
              <ol className="text-sm text-blue-800 space-y-1 list-decimal list-inside">
                <li>Go to <a href="https://appleid.apple.com" target="_blank" rel="noopener noreferrer" className="underline">appleid.apple.com</a></li>
                <li>Sign in with your Apple ID</li>
                <li>Go to Sign-In and Security</li>
                <li>Click on App-Specific Passwords</li>
                <li>Generate a new password for "Calendar Assistant"</li>
              </ol>
            </div>

            <button
              onClick={() => router.push('/dashboard')}
              className="block mx-auto mt-4 text-gray-500 hover:text-gray-700 text-sm"
            >
              Back to Dashboard
            </button>
          </>
        )}

        {status === 'connecting' && (
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
            <p className="text-gray-600">Connecting to iCloud Calendar...</p>
          </div>
        )}

        {status === 'success' && (
          <div className="text-center">
            <div className="text-green-500 text-5xl mb-4">&#10003;</div>
            <p className="text-green-600 font-medium">Successfully connected!</p>
            <p className="text-gray-500 text-sm mt-2">Redirecting to dashboard...</p>
          </div>
        )}

        {status === 'error' && (
          <div className="text-center">
            <div className="text-red-500 text-5xl mb-4">&#10005;</div>
            <p className="text-red-600 font-medium mb-4">{error}</p>
            <button
              onClick={() => {
                setStatus('form')
                setError(null)
              }}
              className="bg-gray-900 text-white px-6 py-2 rounded-lg hover:bg-gray-800 transition"
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

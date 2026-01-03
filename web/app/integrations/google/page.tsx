'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://corben.pro'

export default function GoogleIntegration() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'connecting' | 'success' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const errorParam = searchParams.get('error')

    if (errorParam) {
      setStatus('error')
      setError('Authorization was cancelled or denied')
      return
    }

    if (code) {
      // We have an authorization code, exchange it for tokens
      handleCallback(code, state)
    } else {
      // No code, start OAuth flow
      startOAuthFlow()
    }
  }, [searchParams])

  const startOAuthFlow = async () => {
    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/')
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/integrations/google/auth`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        throw new Error('Failed to get authorization URL')
      }

      const data = await response.json()
      // Store state for verification
      localStorage.setItem('oauth_state', data.state)
      // Redirect to Google
      window.location.href = data.authorization_url
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Failed to start authorization')
    }
  }

  const handleCallback = async (code: string, state: string | null) => {
    setStatus('connecting')

    const token = localStorage.getItem('token')
    const savedState = localStorage.getItem('oauth_state')

    if (!token) {
      router.push('/')
      return
    }

    // Verify state
    if (state && savedState && state !== savedState) {
      setStatus('error')
      setError('Invalid OAuth state. Please try again.')
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/integrations/google/callback`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code, state }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to connect Google Calendar')
      }

      localStorage.removeItem('oauth_state')
      setStatus('success')

      // Redirect to dashboard after short delay
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
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          Google Calendar
        </h1>

        {status === 'loading' && (
          <div>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Redirecting to Google...</p>
          </div>
        )}

        {status === 'connecting' && (
          <div>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Connecting your calendar...</p>
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
                setStatus('loading')
                setError(null)
                startOAuthFlow()
              }}
              className="bg-blue-500 text-white px-6 py-2 rounded-lg hover:bg-blue-600 transition"
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
